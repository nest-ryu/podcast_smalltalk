import os
import json
import streamlit as st
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from config import AUDIO_DIR, EPISODES_JSON


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
# 오디오 파일 찾기: 여러 패턴 시도
lesson_num = lesson["lesson"]
audio_found = False

# 패턴 1: "{번호}. {제목}.mp3"
try:
    korean_title = title_ko if title_ko else title_en
    audio_filename = f"{lesson_num}. {korean_title}.mp3"
    audio_path = os.path.join(AUDIO_DIR, audio_filename)
    if os.path.exists(audio_path):
        st.audio(audio_path)
        audio_found = True
except:
    pass

# 패턴 2: "{번호}.mp3" 또는 다른 패턴들 시도
if not audio_found:
    for audio_file in os.listdir(AUDIO_DIR):
        if audio_file.lower().endswith('.mp3'):
            # 파일명이 숫자로 시작하는지 확인
            if audio_file.startswith(f"{lesson_num}.") or audio_file.startswith(f"{lesson_num:03d}."):
                audio_path = os.path.join(AUDIO_DIR, audio_file)
                st.audio(audio_path)
                audio_found = True
                break

if not audio_found:
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
