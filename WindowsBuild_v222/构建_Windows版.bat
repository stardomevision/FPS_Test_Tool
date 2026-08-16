@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM  FPS Test Tool v2.2.2 · Windows 一键构建脚本 (onedir 模式)
REM  功能：
REM    1. 自动检测并安装 Python 依赖 (PyInstaller 等)
REM    2. 自动下载 Windows 版 Android platform-tools (adb.exe + DLL)
REM    3. 自动拷贝资源、源代码、图标到构建根目录
REM    4. 调用 PyInstaller 打包 (onedir + COLLECT)
REM    5. 产物校验 (EXE 存在性 + 内置 ADB 存在性)
REM    6. 自动生成发布压缩包 (ZIP) + SHA256 校验
REM  使用:
REM    把本文件放 Windows 任意目录，右键 → 以管理员身份运行 (可选)
REM    或直接双击 (普通权限通常也足够)
REM ============================================================

set "VER=v2.2.2"
set "ARCH=Windows-x64"
set "APP_NAME=星穹视界帧率测试"
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo ============================================================
echo   FPS Test Tool %VER% · Windows 一键构建 (onedir)
echo   %DATE% %TIME%
echo ============================================================
echo.

REM ------------------------------------------------------------
REM Step 1. 检查 Python
REM ------------------------------------------------------------
echo [1/7] 检查 Python 环境 ...
where python >nul 2>nul
if errorlevel 1 (
    echo   错误: 未检测到 python，请先安装 Python 3.10+ (64-bit)
    echo   下载: https://www.python.org/downloads/windows/
    echo   安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "delims=" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   Python 版本: %PYVER%
echo.

REM ------------------------------------------------------------
REM Step 2. 安装 Python 依赖 (PyInstaller + 项目 requirements)
REM ------------------------------------------------------------
echo [2/7] 安装 Python 依赖 ...

echo   ① PyInstaller ...
python -m pip install --upgrade pip >nul
python -m pip install pyinstaller 2>nul | findstr /C:"already satisfied" /C:"Successfully installed"

REM 如果源代码目录有 requirements.txt 就安装里面的依赖
set REQ="%ROOT%源代码\requirements.txt"
if exist %REQ% (
    echo   ② requirements.txt 依赖 ...
    python -m pip install -r %REQ% 2>nul | findstr /C:"already satisfied" /C:"Successfully installed"
)
echo.

REM ------------------------------------------------------------
REM Step 3. 拷贝源代码 / 资源 到构建根目录 (便于 spec 统一访问)
REM ------------------------------------------------------------
echo [3/7] 拷贝源代码和资源文件 ...

if not exist "%ROOT%源代码" (
    echo   错误: 未找到「源代码」目录，请确认构建包结构完整
    pause
    exit /b 2
)

echo   ① 拷贝源代码 (main.py 等) ...
for %%f in (main.py main_window.py adb_client.py ios_client.py fps_analyzer.py db_manager.py device_checker.py app_logger.py requirements.txt) do (
    if exist "%ROOT%源代码\%%f" (
        copy /y "%ROOT%源代码\%%f" "%ROOT%%%f" >nul
    )
)

echo   ② 拷贝 resources 图标目录 ...
if exist "%ROOT%resources\" (
    echo      resources 已在根目录，跳过
) else if exist "%ROOT%源代码\resources\" (
    xcopy /E /I /Y /Q "%ROOT%源代码\resources" "%ROOT%resources" >nul
) else if exist "%ROOT%资源文件\resources\" (
    xcopy /E /I /Y /Q "%ROOT%资源文件\resources" "%ROOT%resources" >nul
) else if exist "%ROOT%资源文件\" (
    if not exist "%ROOT%resources" mkdir "%ROOT%resources"
    for %%i in (png jpg jpeg ico) do (
        copy /y "%ROOT%资源文件\*.%%i" "%ROOT%resources\" >nul 2>nul
    )
)

echo   ③ 拷贝 .spec 到根目录 ...
copy /y "%ROOT%源代码\%APP_NAME%_Windows.spec" "%ROOT%%APP_NAME%_Windows.spec" >nul
echo.

REM ------------------------------------------------------------
REM Step 4. 自动下载 Windows platform-tools (adb.exe)
REM ------------------------------------------------------------
echo [4/7] 准备 Windows platform-tools (adb.exe + DLL) ...

if exist "%ROOT%platform-tools\adb.exe" (
    echo      已存在 platform-tools\adb.exe，跳过下载
) else (
    echo      下载 Windows 版 platform-tools-latest-windows.zip ...
    set "ZIP=%ROOT%pt_windows.zip"
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile '%ZIP%'"
    if not exist "%ZIP%" (
        echo      [Warn] 自动下载失败，请手动下载后解压到根目录:
        echo             https://dl.google.com/android/repository/platform-tools-latest-windows.zip
    ) else (
        echo      解压到 platform-tools\ ...
        powershell -NoProfile -Command "Expand-Archive -Force -LiteralPath '%ZIP%' -DestinationPath '%ROOT%'"
        del /q /f "%ZIP%" 2>nul
    )
)

REM 校验 platform-tools 关键文件
set "ADB_OK=0"
if exist "%ROOT%platform-tools\adb.exe" if exist "%ROOT%platform-tools\AdbWinApi.dll" set "ADB_OK=1"
if "%ADB_OK%"=="1" (
    echo      platform-tools 已就绪: adb.exe + AdbWinApi.dll
) else (
    echo      [Warn] platform-tools 不完整，打包后可能提示找不到 ADB
    echo             请手动下载解压 platform-tools 目录到本脚本同级
)
echo.

REM ------------------------------------------------------------
REM Step 5. 清理旧构建 → 执行 PyInstaller
REM ------------------------------------------------------------
echo [5/7] PyInstaller 打包 (onedir 模式，需要 5~15 分钟) ...

if exist "%ROOT%build" rd /s /q "%ROOT%build" 2>nul
if exist "%ROOT%dist"  rd /s /q "%ROOT%dist"  2>nul

set "BUILD_LOG=%ROOT%build_%VER%_%ARCH%.log"
echo. > "%BUILD_LOG%"
echo   实时日志: %BUILD_LOG%
echo.

python -u -m PyInstaller --noconfirm --clean "%ROOT%%APP_NAME%_Windows.spec" >> "%BUILD_LOG%" 2>&1
set ERR=%ERRORLEVEL%

echo.
if %ERR% NEQ 0 (
    echo   [错误] PyInstaller 返回码 %ERR%，请查看日志文件：
    echo          %BUILD_LOG%
    pause
    exit /b 3
)

REM ------------------------------------------------------------
REM Step 6. 产物校验
REM ------------------------------------------------------------
echo [6/7] 产物校验 ...

set "OUT_DIR=%ROOT%dist\%APP_NAME%"
set "EXE=%OUT_DIR%\%APP_NAME%.exe"
set "ADB_INT=%OUT_DIR%\_internal\platform-tools\adb.exe"

if not exist "%EXE%" (
    echo   [错误] 未找到 EXE：%EXE%
    pause
    exit /b 4
)

for %%A in ("%EXE%") do set "EXE_SIZE=%%~zA"
set /a EXE_MB=%EXE_SIZE%/1048576
echo   ✓ EXE 存在：%APP_NAME%.exe (%EXE_MB% MB)

if exist "%ADB_INT%" (
    echo   ✓ 内置 ADB 存在：_internal\platform-tools\adb.exe
) else (
    echo   ℹ  提示: 未在 _internal\ 中找到 ADB（若 platform-tools 是运行时放置也 OK）
)
echo.

REM ------------------------------------------------------------
REM Step 7. 压缩发布包 + SHA256 校验
REM ------------------------------------------------------------
echo [7/7] 生成发布压缩包 + SHA256 校验 ...

set "RELEASE_DIR=%ROOT%Release_%VER%"
if exist "%RELEASE_DIR%" rd /s /q "%RELEASE_DIR%" 2>nul
mkdir "%RELEASE_DIR%"

set "ZIP_NAME=FPS_Test_Tool-%VER%-%ARCH%.zip"
set "SHA_NAME=FPS_Test_Tool-%VER%-%ARCH%.sha256.txt"

echo   ① 压缩 EXE 目录为 ZIP (点击即用，解压后双击 %APP_NAME%.exe)
powershell -NoProfile -Command "Compress-Archive -Force -CompressionLevel Optimal -Path '%OUT_DIR%' -DestinationPath '%RELEASE_DIR%\%ZIP_NAME%'"

if not exist "%RELEASE_DIR%\%ZIP_NAME%" (
    echo   [Warn] 压缩失败，直接保留 dist\ 目录作为产物
    copy "%EXE%" "%RELEASE_DIR%\" >nul
) else (
    for %%Z in ("%RELEASE_DIR%\%ZIP_NAME%") do set ZS=%%~zZ
    set /a ZSMB=!ZS!/1048576
    echo     大小: !ZSMB! MB
)

echo   ② SHA256 校验 ...
pushd "%RELEASE_DIR%"
powershell -NoProfile -Command "Get-FileHash -Algorithm SHA256 *.zip *.txt 2>$null | ForEach-Object { '{0}  {1}' -f $_.Hash, $_.Path.Substring($_.Path.LastIndexOf('\')+1) }" > "%SHA_NAME%" 2>nul
popd
if exist "%RELEASE_DIR%\%ZIP_NAME%" (
    echo     已生成: %SHA_NAME%
    echo.
    type "%RELEASE_DIR%\%SHA_NAME%"
    echo.
)

echo.
echo ============================================================
echo   构建完成 %VER%  ✅
echo ============================================================
echo.
echo   📦 产物位置:
echo      - 目录版: %OUT_DIR%\
echo                 双击 %APP_NAME%.exe 即可运行（点击即用，无需安装）
echo      - 压缩版: %RELEASE_DIR%\%ZIP_NAME%
echo                 可分发或上传 Release
echo   📄 日志: %BUILD_LOG%
echo.
echo   📧 反馈邮箱: stardomevision@outlook.com
echo   🐙 GitHub  : https://github.com/stardomevision/FPS_Test_Tool
echo.
pause
