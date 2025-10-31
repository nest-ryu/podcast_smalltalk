import os
import subprocess
import streamlit as st
from config import PDF_DIR, AUDIO_DIR, EPISODES_JSON, BASE_DIR
from make_episodes_json import add_pdf_to_json, build_json_from_all_pdfs


def count_git_tracked_files(directory: str, extensions: tuple) -> int:
    """Git에 추적되는 파일만 카운트 (서버에 존재하는 파일)"""
    try:
        # Git에 추적되는 파일 목록 가져오기
        result = subprocess.run(
            ['git', 'ls-files', directory],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            tracked_files = result.stdout.strip().split('\n')
            # 빈 문자열 제거 및 확장자 필터링
            tracked_files = [
                f for f in tracked_files 
                if f and any(f.lower().endswith(ext) for ext in extensions)
            ]
            return len(tracked_files)
    except Exception:
        pass
    
    # Git 명령 실패 시 로컬 파일 시스템 사용 (fallback)
    if os.path.exists(directory):
        return len([f for f in os.listdir(directory) if any(f.lower().endswith(ext) for ext in extensions)])
    return 0


def get_git_tracked_files(directory: str, extensions: tuple) -> list:
    """Git에 추적되는 파일 목록 반환 (서버에 존재하는 파일)"""
    try:
        result = subprocess.run(
            ['git', 'ls-files', directory],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            tracked_files = result.stdout.strip().split('\n')
            # 빈 문자열 제거 및 확장자 필터링, 파일명만 추출
            file_list = [
                os.path.basename(f) for f in tracked_files 
                if f and any(f.lower().endswith(ext) for ext in extensions)
            ]
            return sorted(file_list)
    except Exception:
        pass
    
    # Git 명령 실패 시 로컬 파일 시스템 사용 (fallback)
    if os.path.exists(directory):
        return sorted([f for f in os.listdir(directory) if any(f.lower().endswith(ext) for ext in extensions)])
    return []


# ---------------------------
# 기본 설정
# ---------------------------
st.set_page_config(page_title="Workbook Upload | Podcast Smalltalk", page_icon="📤", layout="wide")
st.title("📤 Workbook Upload | 학습지 업로드")
st.markdown("PDF 학습지와 오디오 파일을 업로드할 수 있습니다.")


# ---------------------------
# PDF 업로드 섹션
# ---------------------------
st.header("📄 PDF 학습지 업로드")
st.markdown("PDF 파일을 업로드하면 자동으로 레슨을 추출하여 JSON 파일이 업데이트됩니다.")

uploaded_pdf = st.file_uploader(
    "PDF 파일 선택",
    type=["pdf"],
    help="학습지 PDF 파일을 업로드하세요."
)

if uploaded_pdf is not None:
    # PDF 파일 정보 표시
    st.info(f"📄 선택된 파일: {uploaded_pdf.name} ({uploaded_pdf.size:,} bytes)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 PDF 저장 및 JSON 업데이트", type="primary", use_container_width=True):
            try:
                # PDF 저장
                pdf_path = os.path.join(PDF_DIR, uploaded_pdf.name)
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_pdf.getbuffer())
                
                st.success(f"✅ PDF 파일이 저장되었습니다: {pdf_path}")
                
                # JSON 업데이트
                with st.spinner("JSON 파일 업데이트 중..."):
                    add_pdf_to_json(pdf_path)
                
                st.success("✅ JSON 파일이 업데이트되었습니다!")
                st.info("💡 메인 페이지로 돌아가서 새로 업로드된 학습지를 확인하세요.")
                
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
    
    with col2:
        if st.button("🔄 전체 JSON 재생성", use_container_width=True):
            try:
                with st.spinner("모든 PDF 파일로부터 JSON 재생성 중..."):
                    build_json_from_all_pdfs()
                st.success("✅ 전체 JSON 파일이 재생성되었습니다!")
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")


# ---------------------------
# 오디오 업로드 섹션
# ---------------------------
st.header("🎧 오디오 파일 업로드")
st.markdown("MP3 오디오 파일을 업로드하세요. 파일명은 '숫자. 제목.mp3' 형식을 권장합니다.")

uploaded_audio = st.file_uploader(
    "오디오 파일 선택",
    type=["mp3", "wav", "m4a"],
    help="오디오 파일을 업로드하세요."
)

if uploaded_audio is not None:
    # 오디오 파일 정보 표시
    file_size = uploaded_audio.size / (1024 * 1024)  # MB
    st.info(f"🎧 선택된 파일: {uploaded_audio.name} ({file_size:.2f} MB)")
    
    # 오디오 미리 듣기
    st.audio(uploaded_audio, format=uploaded_audio.type)
    
    if st.button("💾 오디오 파일 저장", type="primary", use_container_width=True):
        try:
            # 오디오 저장
            audio_path = os.path.join(AUDIO_DIR, uploaded_audio.name)
            with open(audio_path, "wb") as f:
                f.write(uploaded_audio.getbuffer())
            
            st.success(f"✅ 오디오 파일이 저장되었습니다: {audio_path}")
            
        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")


# ---------------------------
# 현재 상태 표시
# ---------------------------
st.markdown("---")
st.header("📊 현재 상태")

col1, col2, col3 = st.columns(3)

with col1:
    if os.path.exists(EPISODES_JSON):
        import json
        with open(EPISODES_JSON, "r", encoding="utf-8") as f:
            episodes = json.load(f)
        st.metric("총 에피소드 수", len(episodes))
    else:
        st.metric("총 에피소드 수", 0)

with col2:
    pdf_count = count_git_tracked_files(PDF_DIR, ('.pdf',))
    st.metric("PDF 파일 수", pdf_count)

with col3:
    audio_count = count_git_tracked_files(AUDIO_DIR, ('.mp3', '.wav', '.m4a'))
    st.metric("오디오 파일 수", audio_count)


# ---------------------------
# 파일 목록 표시
# ---------------------------
tab1, tab2 = st.tabs(["📄 PDF 파일 목록", "🎧 오디오 파일 목록"])

with tab1:
    pdf_files = get_git_tracked_files(PDF_DIR, ('.pdf',))
    if pdf_files:
        for pdf_file in pdf_files:
            st.text(f"📄 {pdf_file}")
    else:
        st.info("업로드된 PDF 파일이 없습니다. (Git 저장소에 추적되는 파일만 표시)")

with tab2:
    audio_files = get_git_tracked_files(AUDIO_DIR, ('.mp3', '.wav', '.m4a'))
    if audio_files:
        for audio_file in audio_files:
            st.text(f"🎧 {audio_file}")
    else:
        st.info("업로드된 오디오 파일이 없습니다. (Git 저장소에 추적되는 파일만 표시)")

