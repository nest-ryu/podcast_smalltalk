@echo off
REM Python 3.11 가상환경 설정 스크립트

echo ========================================
echo Podcast Smalltalk 가상환경 설정
echo ========================================
echo.

REM Python 3.11 찾기
echo Python 3.11을 찾는 중...

REM 방법 1: py launcher 사용
py -3.11 --version >nul 2>&1
if %errorlevel% == 0 (
    echo [방법 1] py -3.11 사용
    py -3.11 -m venv podcast_env
    goto activate
)

REM 방법 2: python3.11 직접 실행
python3.11 --version >nul 2>&1
if %errorlevel% == 0 (
    echo [방법 2] python3.11 사용
    python3.11 -m venv podcast_env
    goto activate
)

REM 방법 3: 일반 python이 3.11인지 확인
python --version 2>&1 | findstr "3.11" >nul
if %errorlevel% == 0 (
    echo [방법 3] python 사용 (버전 3.11)
    python -m venv podcast_env
    goto activate
)

REM 방법 4: 기본 python 사용 (경고)
echo [경고] Python 3.11을 찾을 수 없습니다.
echo 기본 Python을 사용하여 가상환경을 생성합니다.
python -m venv podcast_env
goto activate

:activate
echo.
echo 가상환경 생성 완료!
echo.
echo 다음 명령으로 가상환경을 활성화하세요:
echo   podcast_env\Scripts\activate
echo.
echo 그 다음 패키지를 설치하세요:
echo   pip install -r requirements.txt
echo.
pause

