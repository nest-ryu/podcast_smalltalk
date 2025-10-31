import json
import re
import os
import pdfplumber
from config import PDF_DIR, EPISODES_JSON


# -------------------------------
# 📄 PDF 텍스트 추출 (pdfplumber 사용)
# -------------------------------
def extract_text(pdf_path):
    """PDF 파일에서 텍스트 추출"""
    text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text.append(page_text)
        return "\n".join(text)
    except Exception as e:
        print(f"❌ 오류: {pdf_path} 처리 실패 - {e}")
        return ""


# -------------------------------
# 🔹 Episode/Lesson 구분
# -------------------------------
def split_lessons(full_text):
    """
    PDF 내 다양한 패턴으로 레슨 분리:
    - 'Episode 78 : Chicken Pox'
    - 'DAY 01 — 제목'
    - '78. Chicken Pox'
    """
    # Episode 패턴 먼저 시도 (예: "Episode 78 : Chicken Pox")
    pattern = r"Episode\s*(\d{1,3})\s*[:：]\s*(.+?)(?=\n)"
    matches = list(re.finditer(pattern, full_text, re.MULTILINE | re.IGNORECASE))
    
    if matches:
        lessons = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            lesson_num = int(m.group(1))
            title = m.group(2).strip()
            body = full_text[start:end].strip()
            lessons.append((lesson_num, title, body))
        return lessons
    
    # DAY 패턴 시도
    pattern = r"DAY\s*(\d{1,2})\s*[—-]\s*(.+?)(?=\n|$)"
    matches = list(re.finditer(pattern, full_text, re.MULTILINE))
    
    if matches:
        lessons = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            lesson_num = int(m.group(1))
            title = m.group(2).strip()
            body = full_text[start:end].strip()
            lessons.append((lesson_num, title, body))
        return lessons
    
    # 숫자로 시작하는 패턴 (예: "78. Chicken Pox")
    pattern2 = r"^(\d{1,3})\.\s*(.+?)(?=\n|$)"
    matches2 = list(re.finditer(pattern2, full_text, re.MULTILINE))
    if matches2:
        lessons = []
        for i, m in enumerate(matches2):
            start = m.end()
            end = matches2[i + 1].start() if i + 1 < len(matches2) else len(full_text)
            lesson_num = int(m.group(1))
            title = m.group(2).strip()
            body = full_text[start:end].strip()
            lessons.append((lesson_num, title, body))
        return lessons
    
    # 전체를 하나의 레슨으로 처리 (제목을 파일명에서 추출)
    return [(1, "제목 없음", full_text)]


# -------------------------------
# 🔹 텍스트 정리 함수
# -------------------------------
def clean_text(text):
    if not text:
        return ""
    # 불필요한 라벨 제거 (영문+한글)
    text = re.sub(r"^\s*[|.\-·]*\s*(English Sentences?|영어 문장).*", "", text, flags=re.I | re.M)
    text = re.sub(r"^\s*[|.\-·]*\s*(Korean Translation|한국어 번역).*", "", text, flags=re.I | re.M)
    text = re.sub(r"^\s*[|.\-·]*\s*(Grammar.*|문법.*|표현 포인트.*)", "", text, flags=re.I | re.M)
    text = re.sub(r"^\s*[|.\-·]*\s*(Speaking Practice|말하기 연습|연습).*", "", text, flags=re.I | re.M)
    # 깨끗하게 정리
    return text.strip(" \n\t|·")


def clean_list(lst):
    cleaned = []
    for item in lst:
        t = clean_text(item)
        if t:
            cleaned.append(t)
    return cleaned


# -------------------------------
# 🔹 각 Lesson 내 섹션 추출
# -------------------------------
def extract_sections(body_text):
    """
    본문에서 네 섹션을 분리:
    - 영어 문장 (원본 스크립트/영어 문장)
    - 한국어 번역 (상세 해석/한국어 번역)
    - 문법·표현 포인트 (주요 표현 정리/문법)
    - 말하기 연습 (Daily Mission/말하기 연습)
    """
    # 섹션 분리: A:, B: 패턴으로 찾기
    # 영어 대화 찾기: 첫 번째 A:, B:부터 시작, 한글 문자가 나오기 전까지
    # 또는 "주요 표현" 전까지
    first_english = re.search(r'(A:|B:).*?(?=주요\s*표현|Daily\s*Mission|$)', 
                             body_text, re.DOTALL)
    if first_english:
        english_raw = first_english.group(0).strip()
        # 영어 대화에 한글이 포함되어 있으면 분리
        # 한글 문자가 포함된 마지막 줄 이전까지가 영어
        lines = english_raw.split('\n')
        english_lines = []
        korean_in_english = ""
        for line in lines:
            # 한글이 포함된 줄은 한국어 섹션에 포함
            if re.search(r'[가-힣]', line):
                korean_in_english += line + '\n'
            else:
                # 영어 줄이면 영어에 추가
                if line.strip() and not line.strip().startswith('대화 해석'):
                    english_lines.append(line)
        english_raw = '\n'.join(english_lines).strip()
        # 한국어 부분 저장 (나중에 사용)
        temp_korean = korean_in_english.strip()
    else:
        english_raw = ""
        temp_korean = ""
    
    # 한국어 대화 찾기: 영어 다음의 한글 A:, B: 패턴
    # 또는 이미 영어 섹션에서 추출한 한국어 사용
    if temp_korean:
        korean_raw = temp_korean
    else:
        # 영어 대화 다음 위치에서 한국어 찾기
        if english_raw:
            english_end_pos = body_text.find(english_raw) + len(english_raw)
            rest_text = body_text[english_end_pos:]
            # "주요 표현" 전까지의 한글 A:, B: 패턴
            korean_match = re.search(r'(A:|B:).*?(?=주요\s*표현|Daily\s*Mission|문법|$)', 
                                   rest_text, re.DOTALL)
            if korean_match:
                korean_text = korean_match.group(0)
                # 한글이 포함된 부분만
                korean_lines = [line for line in korean_text.split('\n') 
                              if re.search(r'[가-힣]', line)]
                korean_raw = '\n'.join(korean_lines).strip()
            else:
                korean_raw = ""
        else:
            korean_raw = ""
    
    # expressions 섹션: "주요 표현 정리" 다음부터 "핵심 포인트 요약" 또는 "Daily Mission" 이전까지
    expressions_match = re.search(r'(?:주요\s*표현\s*정리|문법|표현\s*정리)[^\n]*\n(.*?)(?=핵심\s*포인트\s*요약|Daily\s*Mission|말하기|연습|$)', 
                                 body_text, re.IGNORECASE | re.DOTALL)
    expressions_raw = expressions_match.group(1).strip() if expressions_match else ""
    
    # keypoints 섹션: "핵심 포인트 요약" 다음부터 "Daily Mission" 또는 "꼀aily Mission" 이전까지
    # 여러 패턴 시도하여 모든 내용 추출
    keypoints_patterns = [
        r'핵심\s*포인트\s*요약[^\n]*\n(.*?)(?=꼀aily\s*Mission|Daily\s*Mission|말하기|연습|$)',  # 꼀aily 포함
        r'핵심\s*포인트\s*요약[^\n]*\n(.*?)(?=Daily\s*Mission|말하기|연습|$)',  # 기본 패턴
        r'핵심\s*포인트[^\n]*\n(.*?)(?=꼀aily|Daily|말하기|연습|$)',  # 더 넓은 패턴
    ]
    
    keypoints_raw = ""
    for pattern in keypoints_patterns:
        keypoints_match = re.search(pattern, body_text, re.IGNORECASE | re.DOTALL)
        if keypoints_match:
            candidate = keypoints_match.group(1).strip()
            # 더 긴 내용을 선택 (더 많은 항목 포함)
            if len(candidate) > len(keypoints_raw):
                keypoints_raw = candidate
    
    # fallback: 직접 찾기 방식으로 더 확실하게 추출 (항상 실행)
    # 정규식 방식이 불완전할 수 있으므로 직접 문자열 찾기로도 시도
    # "핵심 포인트 요약" 또는 "핵심 포인트" 문자열 위치 찾기
    pos = body_text.find("핵심 포인트 요약")
    if pos == -1:
        pos = body_text.find("핵심 포인트")
    
    if pos != -1:
        # 해당 위치 다음부터 "Daily" 또는 "꼀aily" 이전까지
        after_keypoints = body_text[pos:]
        
        # 종료 마커 찾기 (우선순위: Daily Mission 관련이 먼저)
        end_pos = len(after_keypoints)
        # Daily Mission 관련 마커를 먼저 찾기
        for end_marker in ["꼀aily Mission", "Daily Mission"]:
            marker_pos = after_keypoints.find(end_marker)
            if marker_pos != -1 and marker_pos < end_pos:
                end_pos = marker_pos
        
        # Daily Mission이 없으면 다른 마커 찾기
        if end_pos == len(after_keypoints):
            for end_marker in ["꼀aily", "Daily", "말하기"]:
                marker_pos = after_keypoints.find(end_marker)
                if marker_pos != -1 and marker_pos < end_pos and marker_pos > 50:  # 너무 앞쪽에 있으면 무시
                    end_pos = marker_pos
        
        # 첫 번째 줄(라벨) 제외하고 나머지 추출
        section_text = after_keypoints[:end_pos]
        lines = section_text.split('\n')
        
        content_lines = []
        found_label = False
        for line in lines:
            if not found_label:
                # "핵심 포인트" 라벨 줄 건너뛰기
                if "핵심" in line and "포인트" in line:
                    found_label = True
                    continue
            else:
                # 빈 줄이 아닌 내용만 추가
                if line.strip():
                    content_lines.append(line.strip())
        
        alternative_content = '\n'.join(content_lines).strip()
        # 더 긴 내용으로 교체 (더 많은 항목 포함)
        if len(alternative_content) > len(keypoints_raw):
            keypoints_raw = alternative_content

    # 영어: 내용만 추출 (라벨은 이미 제거됨)
    # A:, B: 같은 화자 표시는 유지
    english = english_raw.strip()
    
    # 한국어: 내용만 추출, 라벨 제거
    # "대화 해석", "한글 번역" 같은 라벨 제거
    korean = korean_raw.strip()
    # 라벨 제거
    korean = re.sub(r'^대화\s*해석.*?\n', '', korean, flags=re.IGNORECASE)
    korean = re.sub(r'^한글\s*번역.*?\n', '', korean, flags=re.IGNORECASE)
    korean = korean.strip()
    
    # expressions: 리스트로 분리
    expressions = clean_list(expressions_raw.splitlines()) if expressions_raw else []
    
    # keypoints: 리스트로 분리 (완화된 필터링 - 모든 항목 유지)
    if keypoints_raw:
        keypoints_lines = keypoints_raw.splitlines()
        keypoints = []
        for line in keypoints_lines:
            line = line.strip()
            # 빈 줄 제외, 라벨 줄 제외
            if line and not (line.startswith(('핵심', '포인트', '요약')) and '핵심' in line and '포인트' in line):
                # bullet point가 있으면 그대로 유지
                if line.startswith(('•', '-', '*', '·', '□', '▪')):
                    keypoints.append(line)
                elif line:  # bullet point 없어도 내용이 있으면 추가
                    keypoints.append(line)
    else:
        keypoints = []

    return english, korean, expressions, keypoints


# -------------------------------
# 🔹 파일명에서 레슨 번호 추출
# -------------------------------
def extract_lesson_num_from_filename(filename):
    """파일명에서 레슨 번호 추출 (예: "78. Chicken Pox.pdf" -> 78)"""
    import re
    # 파일명에서 숫자 찾기
    match = re.search(r'^(\d{1,3})', os.path.splitext(filename)[0])
    if match:
        return int(match.group(1))
    return None


# -------------------------------
# 🔹 단일 PDF에서 레슨 추출
# -------------------------------
def extract_lessons_from_pdf(pdf_path):
    """단일 PDF 파일에서 레슨들을 추출하여 리스트로 반환"""
    text = extract_text(pdf_path)
    if not text:
        return []
    
    blocks = split_lessons(text)
    lessons = []
    
    # 파일명에서 레슨 번호 추출 (fallback)
    filename_num = extract_lesson_num_from_filename(os.path.basename(pdf_path))
    
    for num, title, body in blocks:
        # 만약 레슨 번호가 1이고 "제목 없음"이면, 파일명에서 추출한 번호 사용
        if num == 1 and title == "제목 없음" and filename_num:
            num = filename_num
            # 파일명에서 제목도 추출 시도
            filename_base = os.path.splitext(os.path.basename(pdf_path))[0]
            if filename_num:
                # "78. Chicken Pox" -> "Chicken Pox" 추출
                title_match = re.search(r'^\d+\.\s*(.+)', filename_base)
                if title_match:
                    title = title_match.group(1).strip()
        
        english, korean, expressions, keypoints = extract_sections(body)
        lessons.append({
            "lesson": num,
            "title": title,
            "english": english,
            "korean": korean,
            "expressions": expressions,
            "keypoints": keypoints,
            "source_pdf": os.path.basename(pdf_path)  # 원본 PDF 파일명 저장
        })
    
    return lessons


# -------------------------------
# 🔹 모든 PDF에서 레슨 수집 및 병합
# -------------------------------
def build_json_from_all_pdfs():
    """
    PDF_DIR에 있는 모든 PDF 파일을 읽어서 레슨을 추출하고,
    lesson 번호로 정렬하여 JSON 파일 생성
    """
    if not os.path.exists(PDF_DIR):
        print(f"❌ PDF 디렉토리가 존재하지 않습니다: {PDF_DIR}")
        return
    
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"⚠️ PDF 파일을 찾을 수 없습니다: {PDF_DIR}")
        # 빈 JSON 파일 생성
        with open(EPISODES_JSON, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        return
    
    all_lessons = []
    
    print(f"📘 {len(pdf_files)}개 PDF 파일 처리 중...")
    for pdf_file in sorted(pdf_files):
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        print(f"  처리 중: {pdf_file}")
        lessons = extract_lessons_from_pdf(pdf_path)
        all_lessons.extend(lessons)
    
    # lesson 번호로 정렬
    all_lessons.sort(key=lambda x: x["lesson"])
    
    # JSON 파일로 저장
    with open(EPISODES_JSON, "w", encoding="utf-8") as f:
        json.dump(all_lessons, f, ensure_ascii=False, indent=2)
    
    print(f"✅ episodes.json 생성 완료 ({len(all_lessons)}개 Episode) → {EPISODES_JSON}")


# -------------------------------
# 🔹 단일 PDF 추가 처리
# -------------------------------
def add_pdf_to_json(pdf_path):
    """
    새로 업로드된 PDF를 처리하여 기존 JSON에 병합
    """
    # 기존 레슨 로드
    existing_lessons = []
    if os.path.exists(EPISODES_JSON):
        with open(EPISODES_JSON, "r", encoding="utf-8") as f:
            existing_lessons = json.load(f)
    
    # 새 PDF에서 레슨 추출
    new_lessons = extract_lessons_from_pdf(pdf_path)
    
    # 기존 레슨과 병합 (중복 제거 - 같은 lesson 번호면 덮어쓰기)
    lesson_dict = {lesson["lesson"]: lesson for lesson in existing_lessons}
    for lesson in new_lessons:
        lesson_dict[lesson["lesson"]] = lesson
    
    # 정렬하여 리스트로 변환
    all_lessons = sorted(lesson_dict.values(), key=lambda x: x["lesson"])
    
    # JSON 파일로 저장
    with open(EPISODES_JSON, "w", encoding="utf-8") as f:
        json.dump(all_lessons, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON 업데이트 완료 (총 {len(all_lessons)}개 Lesson)")
    return len(new_lessons)


# -------------------------------
# 🚀 실행 진입점
# -------------------------------
if __name__ == "__main__":
    import sys
    # Windows 콘솔 인코딩 설정
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("PDF → JSON 변환 시작 (모든 PDF 파일 처리)")
    build_json_from_all_pdfs()
