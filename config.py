import os

# 🔹 프로젝트 기본 경로 (현재 파일 기준)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔹 오디오 파일 경로
AUDIO_DIR = os.path.join(BASE_DIR, "audio")

# 🔹 PDF 학습지 저장 경로 (업로드된 PDF들)
PDF_DIR = os.path.join(BASE_DIR, "pdfs")

# 🔹 임시 다운로드 디렉토리 (YouTube 다운로드용)
TEMP_DOWNLOAD_DIR = os.path.join(BASE_DIR, "temp_downloads")

# 🔹 JSON 데이터 파일
EPISODES_JSON = os.path.join(BASE_DIR, "episodes.json")

# 폴더 자동 생성 (없으면 만들어줌)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

# 🔹 기본 상태 로그
if __name__ == "__main__":
    print("✅ config.py 로드 완료")
    print(f"BASE_DIR       : {BASE_DIR}")
    print(f"AUDIO_DIR      : {AUDIO_DIR}")
    print(f"PDF_DIR        : {PDF_DIR}")
    print(f"EPISODES_JSON   : {EPISODES_JSON}")

