"""
오디오 생성 페이지
YouTube에서 다운로드하고 podcast_cutter로 회화 부분 추출
모든 필요한 코드가 내부에 포함되어 있습니다.
"""
import os
import sys
from pathlib import Path
import streamlit as st
import subprocess
import shutil
import re
import unicodedata
from typing import List, Dict

try:
    from yt_dlp import YoutubeDL
except ImportError:
    st.error("yt-dlp가 설치되어 있지 않습니다. 'pip install yt-dlp'를 실행해주세요.")
    st.stop()

try:
    import whisper
except ImportError:
    st.error("openai-whisper가 설치되어 있지 않습니다. 'pip install openai-whisper'를 실행해주세요.")
    st.stop()

# 프로젝트 루트 경로 (pages/ 상위 기준)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# config 에서 경로를 가져오되, 누락 시 안전한 기본값으로 대체
try:
    from config import AUDIO_DIR, TEMP_DOWNLOAD_DIR
except Exception:
    AUDIO_DIR = os.path.join(BASE_DIR, "audio")
    TEMP_DOWNLOAD_DIR = os.path.join(BASE_DIR, "temp_downloads")
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)


# ============================================================================
# 내장 함수들 (원래 외부 모듈에서 가져오던 것들)
# ============================================================================

def ascii_safe(text: str) -> str:
    """ASCII 안전 문자열 변환"""
    return re.sub(r"[^a-zA-Z0-9 .:-]", "", text)


def transcribe_audio_whisper(src_audio_path, model_size: str = "base"):
    """Whisper를 사용한 음성 인식"""
    model = whisper.load_model(model_size)
    result = model.transcribe(str(src_audio_path), fp16=False, word_timestamps=False)
    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
        for seg in result.get("segments", [])
    ]
    return {
        "text": result.get("text", "").strip(),
        "segments": segments,
        "duration": result.get("duration", None),
    }


def detect_dialogue_with_silence(audio_segment):
    """pydub를 사용한 무음 구간 감지로 회화 구간 찾기"""
    try:
        from pydub import silence
        # 무음 구간 감지 (최소 1.2초, 평균보다 20dB 낮음)
        silence_ranges = silence.detect_silence(
            audio_segment,
            min_silence_len=1200,  # 1.2초
            silence_thresh=audio_segment.dBFS - 20  # 20dB below average
        )
        silence_ranges = [(start/1000, end/1000) for start, end in silence_ranges]
        
        # 회화 구간 추출 (첫 번째 무음 끝 ~ 마지막 무음 시작)
        if len(silence_ranges) >= 2:
            start_t = silence_ranges[0][1]  # 첫 번째 무음 끝
            end_t = silence_ranges[-1][0]   # 마지막 무음 시작
        else:
            # Fallback: 오디오의 10% ~ 90% 구간 사용
            start_t = len(audio_segment) * 0.1 / 1000
            end_t = len(audio_segment) * 0.9 / 1000
        
        return start_t, end_t
    except ImportError:
        # pydub가 없으면 전체 구간 반환
        duration = len(audio_segment) / 1000
        return 0.0, duration


def refine_end_by_transcript(tr_result, min_words_per_seg: int = 3, tail_silence_threshold: float = 1.5) -> float | None:
    """Whisper 결과를 사용하여 끝부분 보정"""
    try:
        segments = tr_result.get("segments", []) or []
        if not segments:
            return None
        def wc(t: str) -> int:
            return len(re.findall(r"\b\w+\b", t))
        speech_like = [s for s in segments if wc(s.get("text", "")) >= min_words_per_seg]
        last_end = (speech_like[-1]["end"] if speech_like else segments[-1]["end"]) or 0.0
        dur = tr_result.get("duration") or last_end
        if (dur - last_end) >= tail_silence_threshold:
            return float(last_end)
        return None
    except Exception:
        return None


def derive_base_name(src: Path) -> str:
    """출력 파일명 생성 (예: '75. paranoid')"""
    stem = src.stem
    
    # 구분자 정규화
    cleaned = stem.replace("|", "-").replace("_", " ")
    
    # 패턴 1: '... - Episode 75', 'Ep75', 'EP 75'
    m = re.search(r"(?i)\b(?:episode|ep)\s*(\d{1,4})\b", cleaned)
    if m:
        num = m.group(1)
        left = cleaned[: m.start()].strip()
        title = left or cleaned
        title = re.sub(r"[^A-Za-z0-9\s.-]", "", title).strip().lower()
        title = re.sub(r"\s+", " ", title)
        return f"{num}. {title}" if title else f"{num}. audio"
    
    # 패턴 2: 파일명의 첫 번째 숫자를 에피소드 번호로 사용
    m = re.search(r"(\d{1,4})", cleaned)
    if m:
        num = m.group(1)
        before = cleaned[: m.start()].strip()
        after = cleaned[m.end() :].strip()
        candidate = before if before else after
        candidate = re.sub(r"^[\s\-–_|]+", "", candidate)
        title = re.sub(r"[^A-Za-z0-9\s.-]", "", candidate).strip().lower()
        title = re.sub(r"\s+", " ", title)
        return f"{num}. {title}" if title else f"{num}. audio"
    
    # 패턴 3: Fallback - 정리된 파일명
    title = re.sub(r"[^A-Za-z0-9\s.-]", "", cleaned).strip().lower()
    title = re.sub(r"\s+", " ", title) or "audio"
    return title


# ============================================================================
# YouTubeAudioDownloader 클래스 (내장)
# ============================================================================

class YouTubeAudioDownloader:
    def __init__(self, download_dir: str = "downloads"):
        """초기화"""
        self.download_dir = download_dir
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        
        # ffmpeg/ffprobe 경로 찾기 (온라인 환경 대응)
        self.ffmpeg_bin = None
        self.ffprobe_bin = None
        ffmpeg_location_dir = None
        
        # 1. 시스템 PATH에서 찾기
        self.ffmpeg_bin = shutil.which("ffmpeg")
        self.ffprobe_bin = shutil.which("ffprobe")
        
        # 2. imageio-ffmpeg에서 찾기 (온라인 환경)
        if not self.ffmpeg_bin:
            try:
                import imageio_ffmpeg as iioff
                self.ffmpeg_bin = iioff.get_ffmpeg_exe()
                # ffprobe도 같은 디렉토리에서 찾기
                if self.ffmpeg_bin:
                    ffmpeg_dir = os.path.dirname(self.ffmpeg_bin)
                    # Windows와 Linux 모두 고려
                    probe_names = ['ffprobe.exe', 'ffprobe']
                    for probe_name in probe_names:
                        probe_path = os.path.join(ffmpeg_dir, probe_name)
                        if os.path.exists(probe_path):
                            self.ffprobe_bin = probe_path
                            break
            except Exception:
                pass
        
        # ffmpeg 경로 설정
        if self.ffmpeg_bin:
            ffmpeg_location_dir = os.path.dirname(self.ffmpeg_bin)
            # 환경 변수 설정 (yt-dlp가 인식하도록)
            os.environ['FFMPEG_BINARY'] = self.ffmpeg_bin
            if self.ffprobe_bin:
                os.environ['FFPROBE_BINARY'] = self.ffprobe_bin
            else:
                # ffprobe를 찾지 못했으면 ffmpeg와 같은 경로에서 찾기 시도
                probe_candidates = [
                    os.path.join(ffmpeg_location_dir, 'ffprobe'),
                    os.path.join(ffmpeg_location_dir, 'ffprobe.exe'),
                    self.ffmpeg_bin.replace('ffmpeg', 'ffprobe').replace('ffmpeg.exe', 'ffprobe.exe')
                ]
                for candidate in probe_candidates:
                    if os.path.exists(candidate):
                        self.ffprobe_bin = candidate
                        os.environ['FFPROBE_BINARY'] = candidate
                        break
        
        # yt-dlp 옵션 설정
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': False,
            'noprogress': True,
            'progress_hooks': [],
            'postprocessor_hooks': [],
        }
        
        # ffmpeg 경로 설정 (여러 방법 시도)
        if ffmpeg_location_dir:
            # 방법 1: 디렉토리 경로
            self.ydl_opts['ffmpeg_location'] = ffmpeg_location_dir
            # 방법 2: 환경 변수 설정
            if self.ffmpeg_bin:
                if 'PATH' not in os.environ or ffmpeg_location_dir not in os.environ['PATH']:
                    os.environ['PATH'] = ffmpeg_location_dir + os.pathsep + os.environ.get('PATH', '')
        
        # ffmpeg/ffprobe 찾기 상태 저장 (경고는 나중에 표시)
        self._ffmpeg_available = self.ffmpeg_bin is not None

        # 진행 표시 훅 연결
        self.ydl_opts['progress_hooks'].append(self._progress_hook)
        self.ydl_opts['postprocessor_hooks'].append(self._postprocessor_hook)
        
        # Streamlit 세션 상태에 진행상황 저장용
        if 'progress' not in st.session_state:
            st.session_state.progress = None

    def _normalize_visible_text(self, text: str) -> str:
        """유니코드 수학 볼드 등 특수 스타일 문자를 일반 문자로 정규화."""
        if not text:
            return ""
        decomposed = unicodedata.normalize('NFKD', text)
        without_marks = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
        normalized_spaces = re.sub(r"\s+", " ", without_marks).strip()
        return normalized_spaces

    def _make_filesafe_title(self, title: str) -> str:
        """Windows에서도 안전한 파일명으로 변환."""
        base = self._normalize_visible_text(title) or "audio"
        base = re.sub(r"[<>:\\/\\|?*\"]", " ", base)
        base = ''.join(ch for ch in base if ch >= ' ')
        base = re.sub(r"\s+", " ", base).strip().rstrip('.')
        if len(base) > 150:
            base = base[:150].rstrip()
        return base or "audio"

    def _progress_hook(self, status_dict: Dict):
        """다운로드 진행상황 표시 훅"""
        status = status_dict.get('status')
        if status == 'downloading':
            downloaded = status_dict.get('downloaded_bytes') or 0
            total = status_dict.get('total_bytes') or status_dict.get('total_bytes_estimate') or 0
            percent = (downloaded / total * 100) if total else 0.0
            speed = status_dict.get('speed')
            eta = status_dict.get('eta')
            
            st.session_state.progress = {
                'percent': percent,
                'speed': speed,
                'eta': eta,
                'downloaded': downloaded,
                'total': total
            }
        elif status == 'finished':
            st.session_state.progress = {'status': 'converting'}
        elif status == 'error':
            st.session_state.progress = {'status': 'error'}

    def _postprocessor_hook(self, pp_dict: Dict):
        """후처리(오디오 변환) 진행 표시 훅"""
        status = pp_dict.get('status')
        pp = pp_dict.get('postprocessor')
        if status == 'started' and pp == 'FFmpegExtractAudio':
            st.session_state.progress = {'status': 'converting'}
        elif status == 'finished' and pp == 'FFmpegExtractAudio':
            st.session_state.progress = {'status': 'completed'}
    
    def _get_videos_from_url(self, channel_url: str, max_results: int = 10) -> List[Dict]:
        """채널 URL로부터 영상 목록 가져오기"""
        channel_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        try:
            with YoutubeDL(channel_opts) as ydl:
                channel_info = ydl.extract_info(channel_url, download=False)
                
                if channel_info and 'entries' in channel_info:
                    videos = []
                    for i, entry in enumerate(channel_info['entries'][:max_results], 1):
                        video_id = entry.get('id')
                        if not video_id:
                            continue
                        title = entry.get('title', '제목 없음')
                        url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"
                        duration = entry.get('duration', 0)
                        
                        videos.append({
                            'index': i,
                            'title': title,
                            'url': url,
                            'id': video_id,
                            'duration': duration
                        })
                    
                    return videos if videos else None
        except Exception as e:
            raise Exception(f"URL에서 영상 목록 가져오기 실패: {e}")
    
    def format_duration(self, seconds) -> str:
        """초를 시간:분:초 형식으로 변환"""
        if not seconds:
            return "알 수 없음"
        
        seconds = int(float(seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def download_video(self, video_url: str, video_title: str = ""):
        """영상을 MP3로 다운로드"""
        # ffmpeg 확인
        if not self.ffmpeg_bin:
            st.error("❌ ffmpeg를 찾을 수 없습니다. imageio-ffmpeg를 설치해주세요: pip install imageio-ffmpeg")
            return None
            
        try:
            st.session_state.progress = {'status': 'downloading', 'percent': 0}
            safe_title = self._make_filesafe_title(video_title or "")
            ydl_opts_local = dict(self.ydl_opts)
            ydl_opts_local['outtmpl'] = os.path.join(self.download_dir, f"{safe_title}.%(ext)s")
            
            # ffmpeg 경로를 다시 확인하여 옵션에 명시적으로 추가
            ffmpeg_dir = os.path.dirname(self.ffmpeg_bin)
            ydl_opts_local['ffmpeg_location'] = ffmpeg_dir
            
            # 환경 변수 설정
            os.environ['FFMPEG_BINARY'] = self.ffmpeg_bin
            if self.ffprobe_bin:
                os.environ['FFPROBE_BINARY'] = self.ffprobe_bin
            else:
                # ffprobe를 다시 찾기 시도
                probe_candidates = [
                    os.path.join(ffmpeg_dir, 'ffprobe'),
                    os.path.join(ffmpeg_dir, 'ffprobe.exe'),
                ]
                for candidate in probe_candidates:
                    if os.path.exists(candidate):
                        self.ffprobe_bin = candidate
                        os.environ['FFPROBE_BINARY'] = candidate
                        break
            
            # 포스트프로세서는 executable 인자를 지원하지 않으므로 
            # ffmpeg_location과 환경 변수만으로 충분함
            
            with YoutubeDL(ydl_opts_local) as ydl:
                ydl.download([video_url])
            # 예상 경로 우선 반환
            expected_path = os.path.join(self.download_dir, f"{safe_title}.mp3")
            if os.path.exists(expected_path):
                return expected_path
            # 폴백: 가장 최근 mp3 파일
            files = os.listdir(self.download_dir)
            mp3_files = [f for f in files if f.endswith('.mp3')]
            if mp3_files:
                mp3_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.download_dir, x)), reverse=True)
                return os.path.join(self.download_dir, mp3_files[0])
            return None
        except Exception as e:
            st.error(f"다운로드 실패: {e}")
            return None


# ============================================================================
# Podcast Cutter 파이프라인 함수
# ============================================================================

def run_podcast_cutter_pipeline(src: Path):
    """podcast_cutter 파이프라인 실행"""
    try:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            try:
                import imageio_ffmpeg as iioff
                ffmpeg_bin = iioff.get_ffmpeg_exe()
            except Exception:
                st.error("ffmpeg를 찾을 수 없습니다. imageio-ffmpeg를 설치해주세요.")
                return None
        
        # Step 1: 40초~160초 구간 자르기
        st.write("  - 40초~160초 구간 추출 중...")
        tmp_rough = src.parent / "_st_tmp_rough.mp3"
        start_sec, end_sec = 40, 160
        duration = end_sec - start_sec
        
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", str(src),
            "-acodec", "libmp3lame", "-b:a", "192k",
            str(tmp_rough),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Step 2: 무음 감지로 회화 구간 찾기
        st.write("  - 무음 구간 감지 중...")
        rough_audio = None
        local_start, local_end = 0.0, duration
        
        # 먼저 pydub 시도 (Python 3.12 이하에서 작동)
        try:
            from pydub import AudioSegment
            rough_audio = AudioSegment.from_file(str(tmp_rough), format="mp3")
            local_start, local_end = detect_dialogue_with_silence(rough_audio)
            st.write(f"  - 감지된 회화 구간: {local_start:.2f}초 ~ {local_end:.2f}초")
        except Exception as pydub_error:
            # pydub 실패 시 ffmpeg의 silencedetect 사용
            try:
                st.write("  - ffmpeg silencedetect로 무음 감지 시도...")
                detect_cmd = [
                    ffmpeg_bin, "-i", str(tmp_rough),
                    "-af", "silencedetect=noise=-20dB:duration=0.5",
                    "-f", "null", "-"
                ]
                result = subprocess.run(
                    detect_cmd, 
                    capture_output=True, 
                    text=True, 
                    stderr=subprocess.STDOUT
                )
                
                # silencedetect 출력 파싱
                silence_starts = []
                silence_ends = []
                for line in result.stderr.split('\n'):
                    if 'silence_start' in line:
                        try:
                            start_time = float(line.split('silence_start: ')[1].split()[0])
                            silence_starts.append(start_time)
                        except:
                            pass
                    elif 'silence_end' in line:
                        try:
                            end_time = float(line.split('silence_end: ')[1].split()[0])
                            silence_ends.append(end_time)
                        except:
                            pass
                
                if silence_starts and silence_ends:
                    local_start = silence_ends[0] if silence_ends else 0.0
                    local_end = silence_starts[-1] if silence_starts else duration
                    if local_end <= local_start:
                        local_start, local_end = 0.0, duration
                    st.write(f"  - 감지된 회화 구간: {local_start:.2f}초 ~ {local_end:.2f}초")
                else:
                    st.warning("무음 구간을 찾지 못했습니다. 전체 구간을 사용합니다.")
                    local_start, local_end = 0.0, duration
            except Exception as ffmpeg_error:
                st.warning(f"무음 감지 실패: {ffmpeg_error}. 전체 구간을 사용합니다.")
                local_start, local_end = 0.0, duration
        
        # Step 3: 회화 부분만 추출
        st.write("  - 회화 부분만 추출 중...")
        tmp_precise = src.parent / "_st_tmp_precise.mp3"
        
        if rough_audio:
            try:
                precise_dialogue = rough_audio[int(local_start*1000):int(local_end*1000)]
                precise_dialogue.export(str(tmp_precise), format="mp3")
            except Exception as e:
                st.warning(f"pydub로 추출 실패, ffmpeg 사용: {e}")
                precise_duration = local_end - local_start
                cmd = [
                    ffmpeg_bin, "-y",
                    "-ss", str(local_start),
                    "-t", str(precise_duration),
                    "-i", str(tmp_rough),
                    "-acodec", "libmp3lame", "-b:a", "192k",
                    str(tmp_precise),
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            precise_duration = local_end - local_start
            cmd = [
                ffmpeg_bin, "-y",
                "-ss", str(local_start),
                "-t", str(precise_duration),
                "-i", str(tmp_rough),
                "-acodec", "libmp3lame", "-b:a", "192k",
                str(tmp_precise),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Step 4: Whisper로 음성 인식 및 끝부분 보정
        st.write("  - 음성 인식 중...")
        tr = transcribe_audio_whisper(tmp_precise, model_size="base")
        refined_end = refine_end_by_transcript(tr)
        
        if refined_end is not None:
            st.write(f"  - 끝부분 보정 적용: {refined_end:.2f}초까지 재컷팅...")
            tmp_precise_ref = src.parent / "_st_tmp_precise_refined.mp3"
            cmd2 = [
                ffmpeg_bin, "-y",
                "-i", str(tmp_precise),
                "-t", str(max(0.2, refined_end)),
                "-acodec", "libmp3lame", "-b:a", "192k",
                str(tmp_precise_ref),
            ]
            subprocess.run(cmd2, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                tmp_precise.unlink(missing_ok=True)
            except Exception:
                pass
            tmp_precise = tmp_precise_ref
        
        # 최종 파일명 생성
        base_name = derive_base_name(src)
        # 'learn english quickly with podcast' 텍스트 제거
        base_name = re.sub(r'\blearn\s*english\s*quickly\s*with\s*podcast\b', '', base_name, flags=re.IGNORECASE)
        base_name = re.sub(r'\s+', ' ', base_name).strip()  # 연속 공백 제거
        mp3_out = src.parent / f"{base_name}.mp3"
        
        # 최종 MP3 저장
        try:
            with open(tmp_precise, "rb") as rf, open(mp3_out, "wb") as wf:
                wf.write(rf.read())
        except Exception as e:
            st.error(f"파일 저장 실패: {e}")
            return None
        
        # 임시 파일 정리
        for tmp_file in [tmp_rough, tmp_precise]:
            try:
                if tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)
            except Exception:
                pass
        
        return mp3_out
        
    except Exception as e:
        st.error(f"파이프라인 실행 오류: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None


# ============================================================================
# Streamlit 페이지 설정 및 UI
# ============================================================================

st.set_page_config(
    page_title="Audio Generator | Podcast Smalltalk",
    page_icon="🎵",
    layout="wide"
)
st.title("🎵 Audio Generator | 오디오 생성")
st.markdown("YouTube에서 다운로드하고 회화 부분을 추출합니다.")

# ffmpeg 설치 확인 안내
try:
    import imageio_ffmpeg as iioff
    ffmpeg_path = iioff.get_ffmpeg_exe()
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        st.success(f"✅ ffmpeg 설치 확인: `{ffmpeg_path}`")
    else:
        st.warning("⚠️ ffmpeg를 찾을 수 없습니다. `pip install imageio-ffmpeg`를 실행해주세요.")
except Exception as e:
    st.error(f"❌ ffmpeg 설치 확인 실패: {e}")
    st.info("💡 **설치 방법:** `pip install imageio-ffmpeg`를 실행하거나 `requirements.txt`의 패키지를 설치하세요.")


# ---------------------------
# YouTube 다운로더 초기화
# ---------------------------
if 'downloader' not in st.session_state:
    st.session_state.downloader = YouTubeAudioDownloader(download_dir=TEMP_DOWNLOAD_DIR)

downloader = st.session_state.downloader


# ---------------------------
# 채널 영상 목록 가져오기
# ---------------------------
st.header("📺 YouTube 채널 영상 선택")

if st.button("🔄 English Podcast Zone 최신 영상 불러오기", type="primary"):
    with st.spinner("채널에서 최신 영상을 가져오는 중..."):
        try:
            videos = downloader._get_videos_from_url(
                "https://www.youtube.com/@EnglishPodcastZone/videos",
                max_results=3
            )
            if videos:
                st.session_state.videos = videos
                st.success(f"✅ {len(videos)}개의 최신 영상을 불러왔습니다!")
            else:
                st.error("❌ 영상을 찾을 수 없습니다.")
                st.session_state.videos = None
        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")
            st.session_state.videos = None


# ---------------------------
# 영상 목록 표시 및 선택
# ---------------------------
if 'videos' not in st.session_state:
    st.session_state.videos = None

if st.session_state.videos:
    st.markdown("---")
    st.subheader(f"📹 영상 목록 ({len(st.session_state.videos)}개)")
    
    selected_video = None
    video_options = {}
    
    for video in st.session_state.videos:
        duration_str = downloader.format_duration(video.get('duration', 0))
        display_title = downloader._normalize_visible_text(video['title'])
        video_label = f"{video['index']}. {display_title} ({duration_str})"
        video_options[video['id']] = video_label
    
    if video_options:
        selected_id = st.radio(
            "다운로드할 영상 선택",
            options=list(video_options.keys()),
            format_func=lambda x: video_options[x],
            index=0
        )
        selected_video = next(v for v in st.session_state.videos if v['id'] == selected_id)
        
        # 선택된 영상 정보 표시
        if selected_video:
            st.info(f"**선택된 영상:** {video_options[selected_id]}")
            st.markdown(f"🔗 [YouTube에서 보기]({selected_video['url']})")
            
            st.markdown("---")
            
            # 다운로드 및 처리 버튼
            if st.button("⬇️ 다운로드 및 회화 추출 시작", type="primary", use_container_width=True):
                # Step 1: YouTube 다운로드
                progress_container = st.container()
                with progress_container:
                    st.subheader("📥 Step 1: YouTube에서 다운로드 중...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.info(f"다운로드 중: {selected_video['title']}")
                    
                    downloaded_file = downloader.download_video(
                        selected_video['url'],
                        selected_video['title']
                    )
                    
                    if not downloaded_file or not os.path.exists(downloaded_file):
                        st.error("❌ 다운로드 실패했습니다.")
                        st.stop()
                    
                    progress_bar.progress(1.0)
                    status_text.success(f"✅ 다운로드 완료: {os.path.basename(downloaded_file)}")
                    
                    # Step 2: Podcast Cutter로 회화 추출
                    st.markdown("---")
                    st.subheader("✂️ Step 2: 회화 구간 추출 중...")
                    
                    # podcast_cutter 파이프라인 실행
                    audio_path = Path(downloaded_file)
                    output_file = run_podcast_cutter_pipeline(audio_path)
                    
                    if output_file and os.path.exists(output_file):
                        st.success("✅ 회화 추출 완료!")
                        
                        # 최종 오디오 파일을 AUDIO_DIR로 이동
                        final_filename = os.path.basename(output_file)
                        final_path = os.path.join(AUDIO_DIR, final_filename)
                        
                        # 파일 이동
                        shutil.move(str(output_file), final_path)
                        
                        st.markdown("---")
                        st.subheader("📥 다운로드")
                        
                        # 오디오 파일 다운로드 버튼
                        with open(final_path, 'rb') as f:
                            audio_data = f.read()
                        
                        st.download_button(
                            label="💾 추출된 오디오 파일 다운로드",
                            data=audio_data,
                            file_name=final_filename,
                            mime="audio/mpeg",
                            type="primary",
                            use_container_width=True
                        )
                        
                        st.info(f"📁 파일이 저장되었습니다: `{final_path}`")
                        
                        # 임시 다운로드 파일 정리
                        try:
                            os.remove(downloaded_file)
                        except Exception:
                            pass
                    else:
                        st.error("❌ 회화 추출 실패했습니다.")
