import os
import json
import re
import subprocess
import streamlit as st
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from config import AUDIO_DIR, EPISODES_JSON, BASE_DIR


# ---------------------------
# 기본 설정
# ---------------------------
st.set_page_config(page_title="Podcast Smalltalk | 학습지", page_icon="📚", layout="wide", initial_sidebar_state="expanded")
st.title("📚 Podcast Smalltalk | 학습지")
st.markdown("🔹 Lesson 번호를 입력하거나 ⏮⏭ 버튼으로 이동하세요.")


# ---------------------------
# 데이터 로드
# ---------------------------
def load_lessons():
    if os.path.exists(EPISODES_JSON):
        with open(EPISODES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    st.error("❌ episodes.json 파일을 찾을 수 없습니다.")
    return []

lessons = load_lessons()
if not lessons:
    st.info("ℹ️ 아직 업로드된 학습지가 없습니다. 업로드 페이지에서 PDF 파일을 업로드해주세요.")
    st.stop()


# ---------------------------
# 세션 상태
# ---------------------------
if "lesson_index" not in st.session_state:
    st.session_state.lesson_index = 0
if "lesson_query" not in st.session_state:
    st.session_state.lesson_query = ""


# ---------------------------
# 입력 콜백: Enter 시 이동 + 입력창 비우기
# ---------------------------
def _on_enter():
    raw = st.session_state.lesson_query.strip().upper().replace("LESSON", "").strip()
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(lessons):
            # lesson 번호로 찾기
            for i, lesson in enumerate(lessons):
                if lesson["lesson"] == n:
                    st.session_state.lesson_index = i
                    break
    # 항상 비워서 공백 유지
    st.session_state.lesson_query = ""


# ---------------------------
# Lesson 번호 입력창
# ---------------------------
st.text_input(
    "Lesson 번호 입력 (예: 78)",
    key="lesson_query",
    placeholder="번호 입력 후 Enter",
    on_change=_on_enter,
)


# ---------------------------
# 이전/다음 버튼
# ---------------------------
c1, c2, csp = st.columns([0.14, 0.14, 0.72])
with c1:
    if st.button("⏮ 이전", use_container_width=True):
        if st.session_state.lesson_index > 0:
            st.session_state.lesson_index -= 1
            st.rerun()
with c2:
    if st.button("⏭ 다음", use_container_width=True):
        if st.session_state.lesson_index < len(lessons) - 1:
            st.session_state.lesson_index += 1
            st.rerun()
with csp:
    current_lesson_num = lessons[st.session_state.lesson_index]["lesson"]
    total_count = len(lessons)
    st.markdown(
        f"<div style='text-align:right;font-weight:700;'>현재 Lesson: {current_lesson_num} / {total_count}개</div>",
        unsafe_allow_html=True,
    )


# ---------------------------
# 현재 선택된 Lesson
# ---------------------------
lesson = lessons[st.session_state.lesson_index]

# 제목 구성: "영문 | 한글"이 들어온 경우 분리
title_en, title_ko = lesson["title"], ""
if "|" in lesson["title"]:
    parts = lesson["title"].split("|", 1)
    title_en = parts[0].strip()
    title_ko = parts[1].strip()

# 버튼 바로 아래 제목 표시
st.markdown(
    f"<h2 style='margin-top:8px;'>Lesson {lesson['lesson']} — {title_en}"
    + (f" | {title_ko}" if title_ko else "")
    + "</h2>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ---------------------------
# 오디오 재생
# ---------------------------
def get_git_tracked_audio_files():
    """Git에 추적되는 오디오 파일 목록 반환"""
    try:
        git_dir = os.path.join(BASE_DIR, '.git')
        if not os.path.exists(git_dir):
            # Git 저장소가 아니면 로컬 파일 시스템 사용
            if os.path.exists(AUDIO_DIR):
                return sorted([f for f in os.listdir(AUDIO_DIR) 
                              if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'))])
            return []
        
        # 상대 경로로 변환
        rel_audio_dir = os.path.relpath(AUDIO_DIR, BASE_DIR).replace('\\', '/')
        
        result = subprocess.run(
            ['git', 'ls-files', rel_audio_dir],
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
                if f and f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'))
            ]
            return sorted(file_list)
    except Exception:
        pass
    
    # Git 명령 실패 시 로컬 파일 시스템 사용 (fallback)
    if os.path.exists(AUDIO_DIR):
        return sorted([f for f in os.listdir(AUDIO_DIR) 
                       if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'))])
    return []


def find_audio_file_for_lesson(lesson_num, title_en="", title_ko=""):
    """레슨 번호에 맞는 오디오 파일 찾기 (다양한 패턴 지원)"""
    audio_files = get_git_tracked_audio_files()
    lesson_num_str = str(lesson_num)
    lesson_num_padded = f"{lesson_num:03d}"  # 001 형식
    
    # 패턴 리스트 (우선순위 순)
    patterns = [
        # 정확한 매칭 패턴들
        f"{lesson_num}.mp3",
        f"{lesson_num_padded}.mp3",
        f"Lesson {lesson_num}.mp3",
        f"lesson-{lesson_num}.mp3",
        
        # 제목 포함 패턴들
        f"{lesson_num}. {title_en}.mp3" if title_en else None,
        f"{lesson_num}. {title_ko}.mp3" if title_ko else None,
        f"{lesson_num_padded}. {title_en}.mp3" if title_en else None,
        f"{lesson_num_padded}. {title_ko}.mp3" if title_ko else None,
    ]
    
    # 패턴 제거 (None 제거)
    patterns = [p for p in patterns if p]
    
    # 패턴 1: 정확한 파일명 매칭
    for pattern in patterns:
        for audio_file in audio_files:
            if audio_file == pattern:
                return os.path.join(AUDIO_DIR, audio_file)
    
    # 패턴 2: 숫자로 시작하는 파일 찾기
    for audio_file in audio_files:
        # 파일명에서 첫 번째 숫자 추출
        match = re.match(r'^(\d+)', audio_file)
        if match:
            file_num = int(match.group(1))
            if file_num == lesson_num:
                return os.path.join(AUDIO_DIR, audio_file)
    
    # 패턴 3: 부분 매칭 (제목 포함)
    if title_en or title_ko:
        search_title = (title_ko if title_ko else title_en).lower()
        for audio_file in audio_files:
            # 레슨 번호로 시작하고 제목이 포함되어 있는지 확인
            if (audio_file.startswith(f"{lesson_num}.") or 
                audio_file.startswith(f"{lesson_num_padded}.")):
                if search_title in audio_file.lower():
                    return os.path.join(AUDIO_DIR, audio_file)
    
    # 패턴 4: 파일명에 레슨 번호가 포함된 경우
    for audio_file in audio_files:
        # "79" 또는 "079" 같은 패턴 찾기
        if (f".{lesson_num}." in audio_file or 
            f"-{lesson_num}." in audio_file or
            f"_{lesson_num}." in audio_file or
            audio_file.startswith(f"{lesson_num}-") or
            audio_file.startswith(f"{lesson_num}_")):
            return os.path.join(AUDIO_DIR, audio_file)
    
    return None


# 오디오 파일 찾기 및 재생
lesson_num = lesson["lesson"]
audio_path = find_audio_file_for_lesson(lesson_num, title_en, title_ko)

if audio_path and os.path.exists(audio_path):
    st.audio(audio_path)
else:
    st.warning(f"🎧 Lesson {lesson_num}에 해당하는 오디오 파일을 찾을 수 없습니다.")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------
# 본문 섹션
# ---------------------------
st.subheader("🗣 영어 문장 | English Sentences")
if lesson.get("english"):
    # 줄간격을 여유있게 조정 (각 줄 사이에 빈 줄 하나 추가)
    english_lines = lesson["english"].split("\n")
    english_with_spacing = "\n\n".join([line for line in english_lines if line.strip()])
    # 글자 크기를 키우기 위해 스타일 추가
    english_html = f'<div style="font-size: 16px; line-height: 1.8;">{english_with_spacing.replace(chr(10), "<br/>")}</div>'
    st.markdown(english_html, unsafe_allow_html=True)
else:
    st.info("영어 문장이 없습니다.")
st.markdown("<br><br>", unsafe_allow_html=True)  # 공백줄 두 줄 추가

st.subheader("🇰🇷 한국어 번역 | Korean Translation")
if lesson.get("korean"):
    # 줄간격을 여유있게 조정 (각 줄 사이에 빈 줄 하나 추가)
    korean_lines = lesson["korean"].split("\n")
    korean_with_spacing = "\n\n".join([line for line in korean_lines if line.strip()])
    # 글자 크기를 키우기 위해 스타일 추가
    korean_html = f'<div style="font-size: 16px; line-height: 1.8;">{korean_with_spacing.replace(chr(10), "<br/>")}</div>'
    st.markdown(korean_html, unsafe_allow_html=True)
else:
    st.info("한국어 번역이 없습니다.")
st.markdown("<br><br>", unsafe_allow_html=True)  # 공백줄 두 줄 추가

if lesson.get("expressions"):
    st.subheader("💡 주요 표현 정리 | Key Expressions")
    for g in lesson["expressions"]:
        st.markdown(f"- {g}")
    st.markdown("<br>", unsafe_allow_html=True)

if lesson.get("keypoints"):
    st.subheader("📝 핵심 포인트 요약 | Key Points")
    for s in lesson["keypoints"]:
        st.markdown(f"- {s}")

# 소스 PDF 정보 표시 (있는 경우)
if lesson.get("source_pdf"):
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(f"📄 원본 파일: {lesson['source_pdf']}")


# ---------------------------
# PDF 생성·다운로드
# ---------------------------
def create_pdf_buffer(lesson_obj):
    # 한글 폰트 등록
    pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
    
    # 스타일 정의
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CompactTitle',
        fontName='HYSMyeongJo-Medium',
        fontSize=13,
        leading=16,
        spaceAfter=10,
        alignment=1
    ))
    styles.add(ParagraphStyle(
        name='CompactHeading',
        fontName='HYSMyeongJo-Medium',
        fontSize=10,
        leading=14,
        spaceAfter=6,
        textColor='#333333'
    ))
    styles.add(ParagraphStyle(
        name='CompactBody',
        fontName='HYSMyeongJo-Medium',
        fontSize=9,
        leading=13,
        spaceAfter=8
    ))
    
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, 
        pagesize=A4,
        rightMargin=50, 
        leftMargin=50, 
        topMargin=40, 
        bottomMargin=40
    )
    story = []

    # 제목
    t_en, t_ko = lesson_obj["title"], ""
    if "|" in t_en:
        p = t_en.split("|", 1)
        t_en, t_ko = p[0].strip(), p[1].strip()
    full_title = f"<b>Lesson {lesson_obj['lesson']} &mdash; {t_en}" + (f" | {t_ko}</b>" if t_ko else "</b>")
    story.append(Paragraph(full_title, styles['CompactTitle']))
    story.append(Spacer(1, 8))

    # 영어 문장
    if lesson_obj.get("english"):
        story.append(Spacer(1, 20))
        story.append(Paragraph("<b>영어 문장 | English Sentences</b>", styles['CompactHeading']))
        story.append(Paragraph(lesson_obj["english"].replace("\n", "<br/>"), styles['CompactBody']))
    
    # 한국어 번역
    if lesson_obj.get("korean"):
        story.append(Spacer(1, 15))
        story.append(Paragraph("<b>한국어 번역 | Korean Translation</b>", styles['CompactHeading']))
        story.append(Paragraph(lesson_obj["korean"].replace("\n", "<br/>"), styles['CompactBody']))
    
    # 주요 표현 정리
    if lesson_obj.get("expressions"):
        story.append(Spacer(1, 15))
        story.append(Paragraph("<b>주요 표현 정리 | Key Expressions</b>", styles['CompactHeading']))
        expressions_text = "<br/>".join([f"&bull; {g}" for g in lesson_obj["expressions"]])
        story.append(Paragraph(expressions_text, styles['CompactBody']))
    
    # 핵심 포인트 요약
    if lesson_obj.get("keypoints"):
        story.append(Spacer(1, 15))
        story.append(Paragraph("<b>핵심 포인트 요약 | Key Points</b>", styles['CompactHeading']))
        keypoints_text = "<br/>".join([f"&bull; {s}" for s in lesson_obj["keypoints"]])
        story.append(Paragraph(keypoints_text, styles['CompactBody']))

    doc.build(story)
    buf.seek(0)
    return buf

pdf_buffer = create_pdf_buffer(lesson)
st.markdown("<br>", unsafe_allow_html=True)
st.download_button(
    label="📄 학습지 PDF 다운로드",
    data=pdf_buffer,
    file_name=f"Lesson_{lesson['lesson']}.pdf",
    mime="application/pdf"
)
