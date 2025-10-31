@echo off
REM Anaconda에서 Python 3.11 conda 환경 생성

echo ========================================
echo Podcast Smalltalk Conda 환경 설정
echo ========================================
echo.

REM 기존 환경 확인
conda env list | findstr "podcast_env" >nul
if %errorlevel% == 0 (
    echo 기존 podcast_env 환경이 발견되었습니다.
    echo.
    set /p recreate="기존 환경을 삭제하고 재생성하시겠습니까? (y/n): "
    if /i "%recreate%"=="y" (
        echo 기존 환경 삭제 중...
        conda env remove -n podcast_env -y
    ) else (
        echo 기존 환경을 사용합니다.
        goto activate
    )
)

echo Python 3.11 conda 환경 생성 중...
conda create -n podcast_env python=3.11 -y

if %errorlevel% == 0 (
    echo.
    echo 가상환경 생성 완료!
    goto activate
) else (
    echo.
    echo 가상환경 생성 실패!
    pause
    exit /b 1
)

:activate
echo.
echo ========================================
echo 다음 명령으로 환경을 활성화하세요:
echo   conda activate podcast_env
echo.
echo 그 다음 패키지를 설치하세요:
echo   pip install -r requirements.txt
echo ========================================
echo.
pause

