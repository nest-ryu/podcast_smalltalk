Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Podcast Smalltalk 가상환경 설정" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Python 3.11을 찾는 중..." -ForegroundColor Cyan

# 방법 1: py launcher 사용
try {
    $version = py -3.11 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[방법 1] py -3.11 사용" -ForegroundColor Green
        py -3.11 -m venv podcast_env
        goto activate
    }
} catch {}

# 방법 2: python3.11 직접 실행
try {
    $version = python3.11 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[방법 2] python3.11 사용" -ForegroundColor Green
        python3.11 -m venv podcast_env
        goto activate
    }
} catch {}

# 방법 3: 일반 python이 3.11인지 확인
try {
    $version = python --version 2>&1
    if ($version -match "3\.11") {
        Write-Host "[방법 3] python 사용 (버전 3.11)" -ForegroundColor Green
        python -m venv podcast_env
        goto activate
    }
} catch {}

# 방법 4: 기본 python 사용 (경고)
Write-Host "[경고] Python 3.11을 찾을 수 없습니다." -ForegroundColor Yellow
Write-Host "기본 Python을 사용하여 가상환경을 생성합니다." -ForegroundColor Yellow
python -m venv podcast_env

:activate
Write-Host ""
Write-Host "가상환경 생성 완료!" -ForegroundColor Green
Write-Host ""
Write-Host "다음 명령으로 가상환경을 활성화하세요:" -ForegroundColor Cyan
Write-Host "  .\podcast_env\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "그 다음 패키지를 설치하세요:" -ForegroundColor Cyan
Write-Host "  pip install -r requirements.txt" -ForegroundColor White
Write-Host ""

