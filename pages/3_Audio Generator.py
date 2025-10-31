"""
오디오 생성 페이지
YouTube에서 다운로드하고 podcast_cutter로 회화 부분 추출
"""
import os
import sys
from pathlib import Path
import streamlit as st
import subprocess
import shutil
from config import AUDIO_DIR, TEMP_DOWNLOAD_DIR

# 상위 디렉토리에서 모듈 import
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
youtube_audio_path = os.path.join(BASE_DIR, 'youtube_audio')
podcast_cutter_path = os.path.join(BASE_DIR, 'podcast_cutter')

sys.path.insert(0, youtube_audio_path)
sys.path.insert(0, podcast_cutter_path)

try:
    from youtube_audio_downloader import YouTubeAudioDownloader
except ImportError as e:
    st.error(f"youtube_audio 모듈을 찾을 수 없습니다: {e}")
    st.info(f"경로: {youtube_audio_path}")
    st.stop()

# podcast_cutter 함수들 import
try:
    import re
    # smalltalk_auto.py에서 직접 함수 import
    from smalltalk_auto import (
        transcribe_audio_whisper,
        detect_dialogue_with_silence,
        refine_end_by_transcript,
        derive_base_name,
        ascii_safe
    )
except ImportError as e:
    st.error(f"podcast_cutter 모듈을 찾을 수 없습니다: {e}")
    st.info(f"경로: {podcast_cutter_path}")
    st.stop()


# ---------------------------
# 함수 정의
# ---------------------------
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
                # ffmpeg silencedetect로 무음 구간 찾기
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
                    # 첫 번째 무음 구간의 끝 ~ 마지막 무음 구간의 시작
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


# ---------------------------
# 기본 설정
# ---------------------------
st.set_page_config(
    page_title="Audio Generator | Podcast Smalltalk",
    page_icon="🎵",
    layout="wide"
)
st.title("🎵 Audio Generator | 오디오 생성")
st.markdown("YouTube에서 다운로드하고 회화 부분을 추출합니다.")


# TEMP_DOWNLOAD_DIR은 config에서 가져옴


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

