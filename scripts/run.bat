@echo off
rem ============================================================
rem  阿鹭 · 一条命令启动可视化语音台（Windows）
rem
rem  用法:
rem    scripts\run.bat               启动 HUD 并打开浏览器
rem    scripts\run.bat --demo        自动演示模式（录屏/验收）
rem    set PORT=9000 && scripts\run.bat   指定端口
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0.."

rem 1) Python 检查
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 ( set "PY=python" ) else (
    echo [错误] 未找到 Python。请先安装 https://www.python.org/downloads/
    echo        安装时务必勾选 "Add Python to PATH"
    pause & exit /b 1
  )
)
%PY% -c "import sys; raise SystemExit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [错误] 需要 Python 3.9 或更高版本
  pause & exit /b 1
)

rem 2) 虚拟环境 + 依赖（幂等）
if not exist .venv (
  echo [1/3] 首次运行：创建虚拟环境 .venv ...
  %PY% -m venv .venv
)
call .venv\Scripts\activate.bat
python -c "import yaml" >nul 2>nul
if errorlevel 1 (
  echo [2/3] 安装依赖 pyyaml ...
  pip install -q -r requirements.txt
)

rem 3) 启动 HUD
if "%PORT%"=="" set PORT=8765
echo.
echo [3/3] 启动阿鹭 HUD -^> http://127.0.0.1:%PORT%
echo       按住 ^(麦克风^) 说话 · Ctrl-C 退出
echo.
if "%1"=="--demo" (
  python -m assistant.hud --demo --port %PORT%
) else (
  python -m assistant.hud --port %PORT%
)
pause
