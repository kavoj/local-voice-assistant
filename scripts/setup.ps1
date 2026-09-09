# ============================================================
# Windows 一键部署入口（PowerShell 5.1+）
#   用法：右键"使用 PowerShell 运行"，或执行：
#     powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# ============================================================
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
Write-Host "== local-voice-assistant 部署（Windows）==" -ForegroundColor Cyan

# 找 Python：优先 py launcher
$python = $null
foreach ($cand in @("py -3", "python3", "python")) {
    try {
        $v = & $cand --version 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -and $v -match "3\.(9|1[0-9])") { $python = $cand; break }
    } catch {}
}
if (-not $python) {
    Write-Error "未找到 Python 3.9+，请先安装：https://www.python.org/downloads/（勾选 Add to PATH）"
}

Write-Host "使用 $python 启动部署向导…"
if ($args.Count -gt 0) {
    & $python scripts\quickstart.py @args
} else {
    & $python scripts\quickstart.py
}
exit $LASTEXITCODE
