# jua-list 설치: jua 명령 PATH 등록 + MCP 등록 + 로그인 시 위젯 자동 실행 + 위젯 실행
# 해제: -Uninstall (시작 프로그램만 뺌)
param([switch]$Uninstall)

$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'jua-list.lnk'
if ($Uninstall) {
    Remove-Item $lnk -ErrorAction SilentlyContinue
    Write-Host "시작 프로그램에서 뺌"
    return
}

$py = (Get-Command python -ErrorAction Stop).Source
& $py (Join-Path $PSScriptRoot 'jua.py') install --mcp --startup
& $py (Join-Path $PSScriptRoot 'jua.py') widget
