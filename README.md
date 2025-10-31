# Podcast Smalltalk 학습지 시스템

스피킹 매트릭스와 같은 구조의 학습지 관리 시스템입니다.

## 기능

1. **학습지 보기**: JSON 파일에서 학습지를 읽어서 순서대로 표시
2. **학습지 업로드**: PDF 및 오디오 파일 업로드
3. **자동 JSON 생성**: PDF 업로드 시 자동으로 레슨 추출 및 JSON 업데이트
4. **정렬된 순서**: 레슨 번호로 자동 정렬되어 표시

## 설치

### Python 버전 요구사항

**Python 3.11 또는 3.12 권장**
- pydub가 audioop 모듈을 필요로 하며, Python 3.13+에서는 audioop가 제거되었습니다
- Python 3.11 또는 3.12를 사용하시면 pydub를 통해 무음 감지 기능을 정상적으로 사용할 수 있습니다
- Python 3.13+를 사용하시면 ffmpeg를 통한 무음 감지로 대체됩니다

### Python 3.11 설치 및 가상환경 설정

#### Anaconda 사용 시 (권장)

**Conda 환경 생성:**
```bash
# Python 3.11 conda 환경 생성
conda create -n podcast_env python=3.11 -y

# 환경 활성화
conda activate podcast_env

# 패키지 설치
pip install -r requirements.txt
```

**자동 스크립트 사용:**
- PowerShell: `.\setup_conda_env.ps1`
- CMD: `setup_conda_env.bat`

**환경 확인:**
```bash
# 환경 활성화 후 Python 버전 확인
conda activate podcast_env
python --version  # Python 3.11.x 확인
```

#### 일반 Python 사용 시

1. **Python 3.11 설치**
   - Python 공식 웹사이트: https://www.python.org/downloads/release/python-3119/
   - Windows installer (64-bit) 다운로드
   - 설치 시 **"Add Python to PATH"** 체크박스 선택

2. **또는 Microsoft Store에서 설치**
   - Microsoft Store 앱에서 "Python 3.11" 검색 후 설치

### 가상환경 설정 (일반 Python)

#### Python 3.11이 기본인 경우:

```bash
# 가상환경 생성
python -m venv podcast_env

# 가상환경 활성화 (Windows PowerShell)
.\podcast_env\Scripts\Activate.ps1

# 가상환경 활성화 (Windows CMD)
podcast_env\Scripts\activate.bat

# 가상환경 활성화 (Linux/Mac)
source podcast_env/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

#### Python 3.11이 별도로 설치된 경우:

```bash
# Python 3.11로 가상환경 생성
py -3.11 -m venv podcast_env

# 또는 전체 경로 지정
C:\Python311\python.exe -m venv podcast_env

# 가상환경 활성화
.\podcast_env\Scripts\Activate.ps1

# 패키지 설치
pip install -r requirements.txt
```

### 직접 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
streamlit run Podcast_Smalltalk.py
```

Streamlit이 자동으로 사이드바에 페이지를 표시합니다:
- **Podcast Smalltalk** (메인 페이지)
- **Workbook Upload** (PDF 및 오디오 파일 업로드)
- **Audio Generator** (오디오 생성)

## 디렉토리 구조

```
podcast_smalltalk/
├── Podcast_Smalltalk.py    # 메인 학습지 보기 페이지
├── pages/
│   └── 2_upload.py         # 업로드 페이지
├── config.py               # 설정 파일
├── make_lessons_json.py    # PDF → JSON 변환 스크립트
├── lessons.json            # 학습지 데이터 (자동 생성)
├── pdfs/                   # 업로드된 PDF 파일들
└── audio/                  # 업로드된 오디오 파일들
```

## 사용 방법

### PDF 업로드

1. **업로드** 페이지로 이동
2. PDF 파일 선택
3. "PDF 저장 및 JSON 업데이트" 버튼 클릭
4. JSON 파일이 자동으로 업데이트되어 학습지에 추가됨

### 오디오 업로드

1. **업로드** 페이지로 이동
2. 오디오 파일 (MP3, WAV, M4A) 선택
3. "오디오 파일 저장" 버튼 클릭
4. 파일명은 `숫자. 제목.mp3` 형식을 권장

### PDF 형식

PDF 파일은 다음 형식 중 하나를 지원합니다:
- `DAY 01 — 제목` 형식
- `78. 제목` 형식 (숫자로 시작)

각 레슨은 다음 섹션을 포함할 수 있습니다:
- 🗣 영어 문장
- 🇰🇷 한국어 번역
- 💡 문법·표현 포인트
- 📝 말하기 연습

## 주의사항

- PDF 파일이 불규칙적으로 업로드되더라도 JSON은 항상 레슨 번호로 정렬됩니다
- 같은 레슨 번호의 PDF를 업로드하면 기존 레슨이 덮어씌워집니다
- 전체 JSON을 재생성하려면 "전체 JSON 재생성" 버튼을 사용하세요



