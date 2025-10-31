Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Podcast Smalltalk Conda 환경 설정" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 기존 환경 확인
$existingEnv = conda env list | Select-String "podcast_env"
if ($existingEnv) {
    Write-Host "기존 podcast_env 환경이 발견되었습니다." -ForegroundColor Yellow
    Write-Host ""
    $recreate = Read-Host "기존 환경을 삭제하고 재생성하시겠습니까? (y/n)"
    if ($recreate -eq "y") {
        Write-Host "기존 환경 삭제 중..." -ForegroundColor Yellow
        conda env remove -n podcast_env -y
    } else {
        Write-Host "기존 환경을 사용합니다." -ForegroundColor Green
        exit 0
    }
}

Write-Host "Python 3.11 conda 환경 생성 중..." -ForegroundColor Cyan

$result = conda create -n podcast_env python=3.11 -y

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "가상환경 생성 완료!" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "다음 명령으로 환경을 활성화하세요:" -ForegroundColor Cyan
    Write-Host "  conda activate podcast_env" -ForegroundColor White
    Write-Host ""
    Write-Host "그 다음 패키지를 설치하세요:" -ForegroundColor Cyan
    Write-Host "  pip install -r requirements.txt" -ForegroundColor White
    Write-Host ""
    Write-Host "Streamlit 실행:" -ForegroundColor Cyan
    Write-Host "  streamlit run podcast_smalltalk.py" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Cyan
}
else {
    Write-Host ""
    Write-Host "가상환경 생성 실패!" -ForegroundColor Red
    exit 1
}

