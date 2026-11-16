@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 汽水音乐·纯血鸿蒙自动攒免费听

echo ========================================
echo   汽水音乐 纯血鸿蒙版 自动看广告攒会员
echo ========================================
echo.

where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3.12 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PYCMD=py -3.12"
        goto :foundpy
    )
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PYCMD=py -3"
        goto :foundpy
    )
)
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYCMD=python"
    goto :foundpy
)
echo [错误] 未找到 Python，请先安装 Python 3.10 以上版本。
pause
exit /b 1

:foundpy
echo [Python] %PYCMD%

if not exist ".venv\Scripts\python.exe" (
    echo [初始化] 创建虚拟环境...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败。
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import rapidocr_onnxruntime" >nul 2>&1
if errorlevel 1 (
    echo [初始化] 安装依赖（首次运行，约需 1-2 分钟）...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络。
        pause
        exit /b 1
    )
)

echo.
echo [提示] 自动发现 hdc 与设备；手机需开 USB 调试或无线调试并保持亮屏。
echo        广告必须实打实看完（约 40-80 秒/条），脚本只替你点按钮。
echo        停止：在运行窗口按 Ctrl + C
echo ========================================
echo.

".venv\Scripts\python.exe" -u hm_free_vip.py %*

echo.
echo 脚本已退出。
pause
