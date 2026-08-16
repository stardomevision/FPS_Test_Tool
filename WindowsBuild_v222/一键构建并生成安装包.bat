@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM  FPS Test Tool v2.2.2 · Windows 终极一键脚本
REM  功能（用户只需双击本文件一次）：
REM    1. 检测 / 安装 Python 3.10+ x64
REM    2. 自动安装 PyInstaller + 项目依赖
REM    3. 自动下载 Windows 版 adb platform-tools
REM    4. 调用 PyInstaller 构建 (onedir)
REM    5. 产物校验 (EXE + 内置 ADB)
REM    6. 自动下载 Inno Setup 6 并编译生成 Setup.exe 安装包
REM       → 用户双击 Setup.exe 即标准 Windows 一键安装：
REM         安装到 Program Files / 桌面快捷方式 / 开始菜单 / 卸载面板
REM    7. 打包分发用 ZIP + SHA256 校验
REM  最终产物（可直接分发 / 上传 Release）：
REM    Release_v2.2.2\
REM     ├─ FPS_Test_Tool_v2.2.2_Windows-x64_Setup.exe   ← 一键安装
REM     ├─ FPS_Test_Tool-v2.2.2-Windows-x64.zip         ← 免安装绿色版
REM     └─ *.sha256.txt
REM ============================================================

set "VER=v2.2.2"
set "ARCH=Windows-x64"
set "APP_NAME=星穹视界帧率测试"
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo ========================================================================
echo   FPS Test Tool %VER% · Windows 终极一键构建 (EXE + Setup.exe)
echo   %DATE% %TIME%
echo ========================================================================
echo.
echo   完成后你会得到：
echo     ① 绿色免安装版 (ZIP) —— 解压即用
echo     ② 标准安装包 Setup.exe —— 一键安装到桌面 / 开始菜单 / 卸载面板
echo.

REM ------------------------------------------------------------
REM Step 1. 检查 Python 3.10+ x64
REM ------------------------------------------------------------
echo [1/9] 检查 Python 环境 ...
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo   未检测到 Python，启动自动安装流程（静默官方下载 + 安装） ...
    echo   正在下载 Python 3.12 installer ...
    set "PYI=%ROOT%python-3.12-amd64.exe"
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile '!PYI!'"
    if exist "!PYI!" (
        echo   正在静默安装 Python 3.12 (为所有用户安装，添加到 PATH，含 pip) ...
        start /wait "" "!PYI!" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_tcltk=1 Include_test=0
        set "ERR=!ERRORLEVEL!"
        del /q /f "!PYI!" 2>nul
        REM 刷新 PATH 以便当前会话可立即调用 python
        for /f "skip=2 tokens=1,2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "PATH=%%C;!PATH!"
        for /f "skip=2 tokens=1,2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "PATH=%%C;!PATH!"
        if not "!ERR!"=="0" (
            echo   [错误] Python 安装失败，请手动安装 https://www.python.org/downloads/windows/
            echo   安装时勾选「Add Python to PATH」
            pause
            exit /b 1
        )
    ) else (
        echo   [错误] 自动下载失败，请手动安装 Python 3.10+ x64
        echo   https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
)
for /f "delims=" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   Python 版本: %PYVER%
echo.

REM ------------------------------------------------------------
REM Step 2. 安装依赖 (PyInstaller + requirements)
REM ------------------------------------------------------------
echo [2/9] 安装 Python 依赖 ...
python -m pip install --upgrade pip >nul
python -m pip install pyinstaller 2>nul | findstr /C:"already satisfied" /C:"Successfully installed"
if exist "%ROOT%源代码\requirements.txt" (
    python -m pip install -r "%ROOT%源代码\requirements.txt" 2>nul | findstr /C:"already satisfied" /C:"Successfully installed"
)
echo.

REM ------------------------------------------------------------
REM Step 3. 拷贝源代码 / 资源
REM ------------------------------------------------------------
echo [3/9] 拷贝源代码和资源文件 ...
if not exist "%ROOT%源代码" (
    echo   错误: 未找到「源代码」目录
    pause
    exit /b 2
)
for %%f in (main.py main_window.py adb_client.py ios_client.py fps_analyzer.py db_manager.py device_checker.py app_logger.py requirements.txt) do (
    if exist "%ROOT%源代码\%%f" copy /y "%ROOT%源代码\%%f" "%ROOT%%%f" >nul
)
REM 图标目录
if not exist "%ROOT%resources\" (
    if exist "%ROOT%源代码\resources\" (
        xcopy /E /I /Y /Q "%ROOT%源代码\resources" "%ROOT%resources" >nul
    ) else if exist "%ROOT%资源文件\resources\" (
        xcopy /E /I /Y /Q "%ROOT%资源文件\resources" "%ROOT%resources" >nul
    ) else if exist "%ROOT%资源文件\" (
        if not exist "%ROOT%resources" mkdir "%ROOT%resources"
        for %%i in (png jpg jpeg ico) do copy /y "%ROOT%资源文件\*.%%i" "%ROOT%resources\" >nul 2>nul
    )
)
REM spec + iss
copy /y "%ROOT%源代码\%APP_NAME%_Windows.spec" "%ROOT%%APP_NAME%_Windows.spec" >nul
if exist "%ROOT%安装包脚本.iss" copy /y "%ROOT%安装包脚本.iss" "%ROOT%安装包脚本.iss" >nul
echo.

REM ------------------------------------------------------------
REM Step 4. 自动下载 platform-tools (adb.exe + DLL)
REM ------------------------------------------------------------
echo [4/9] 准备 platform-tools (adb.exe + AdbWinApi.dll + AdbWinUsbApi.dll) ...
if not exist "%ROOT%platform-tools\adb.exe" (
    echo      下载 Google 官方 platform-tools ...
    set "ZIP=%ROOT%pt_windows.zip"
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile '!ZIP!'"
    if exist "!ZIP!" (
        powershell -NoProfile -Command "Expand-Archive -Force -LiteralPath '!ZIP!' -DestinationPath '%ROOT%'"
        del /q /f "!ZIP!" 2>nul
    ) else (
        echo      [Warn] 自动下载失败，请手动下载解压到: %ROOT%platform-tools\
        echo             https://dl.google.com/android/repository/platform-tools-latest-windows.zip
    )
)
if exist "%ROOT%platform-tools\adb.exe" (
    echo      platform-tools 已就绪
) else (
    echo      [Warn] platform-tools 不完整
)
echo.

REM ------------------------------------------------------------
REM Step 5. PyInstaller 构建 (onedir)
REM ------------------------------------------------------------
echo [5/9] PyInstaller 打包 onedir (预计 5~15 分钟，请耐心等待) ...
if exist "%ROOT%build" rd /s /q "%ROOT%build" 2>nul
if exist "%ROOT%dist"  rd /s /q "%ROOT%dist"  2>nul
set "LOG=%ROOT%build_%VER%_%ARCH%.log"
echo. > "%LOG%"
echo   实时日志: %LOG%
echo.

python -u -m PyInstaller --noconfirm --clean "%ROOT%%APP_NAME%_Windows.spec" >> "%LOG%" 2>&1
set "ERR=%ERRORLEVEL%"

if %ERR% NEQ 0 (
    echo   [错误] PyInstaller 构建失败，查看: %LOG%
    pause
    exit /b 3
)

REM ------------------------------------------------------------
REM Step 6. 产物校验 (EXE + 内置 ADB)
REM ------------------------------------------------------------
echo [6/9] 产物校验 ...
set "OUT=%ROOT%dist\%APP_NAME%"
set "EXE=%OUT%\%APP_NAME%.exe"
set "ADB=%OUT%\_internal\platform-tools\adb.exe"
if not exist "%EXE%" (
    echo   [错误] EXE 未生成: %EXE%
    pause
    exit /b 4
)
for %%A in ("%EXE%") do set SZ=%%~zA
set /a MB=%SZ%/1048576
echo   ✓ EXE 存在: %APP_NAME%.exe (%MB% MB)
if exist "%ADB%" (
    echo   ✓ 内置 ADB 存在: _internal\platform-tools\adb.exe
) else (
    echo   ℹ  提示: platform-tools 会在运行时同级查找
)
echo.

REM ------------------------------------------------------------
REM Step 7. 自动下载 Inno Setup 6 + 编译 Setup.exe
REM ------------------------------------------------------------
echo [7/9] 生成标准 Windows 安装包 (Setup.exe) ...

set "ISCC=%ROOT%innosetup\ISCC.exe"
set "ISS=%ROOT%安装包脚本.iss"

REM ① 若系统已装 Inno Setup 则直接用
set "SYS_ISCC="
for %%P in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) do if exist %%~P set "SYS_ISCC=%%~P"
if defined SYS_ISCC (
    echo      检测到已安装 Inno Setup: %SYS_ISCC%
    set "ISCC=%SYS_ISCC%"
)

REM ② 本地未装 → 自动下载 portable 版 (GitHub 镜像官方)
if not exist "%ISCC%" (
    echo      正在下载 Inno Setup 6 portable ...
    set "IS_ZIP=%ROOT%innosetup.zip"
    REM 使用官方 jrsoftware.org 下载（Inno Setup 官方作者域名）
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://files.jrsoftware.org/is/6/innosetup-6.4.2-dev.zip' -OutFile '!IS_ZIP!'" 2>nul
    REM GitHub releases mirror (备用)
    if not exist "!IS_ZIP!" (
        powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/setup-6_4_2/innosetup-6.4.2-dev.zip' -OutFile '!IS_ZIP!'" 2>nul
    )
    if exist "!IS_ZIP!" (
        powershell -NoProfile -Command "Expand-Archive -Force -LiteralPath '!IS_ZIP!' -DestinationPath '%ROOT%innosetup'"
        del /q /f "!IS_ZIP!" 2>nul
    )
)

REM ③ 编译 Setup.exe
set "SETUPEXE="
if exist "%ISCC%" (
    echo      编译 安装包脚本.iss → Output\FPS_Test_Tool_v2.2.2_Windows-x64_Setup.exe ...
    pushd "%ROOT%"
    "%ISCC%" /Q "%ISS%"  2>&1 | tee -a "%LOG%" >nul
    set "ISERR=!ERRORLEVEL!"
    popd
    if "!ISERR!"=="0" if exist "%ROOT%Output\FPS_Test_Tool_v2.2.2_Windows-x64_Setup.exe" (
        set "SETUPEXE=%ROOT%Output\FPS_Test_Tool_v2.2.2_Windows-x64_Setup.exe"
        for %%S in ("!SETUPEXE!") do set SS=%%~zS
        set /a SMB=!SS!/1048576
        echo      ✓ Setup.exe 生成成功 (!SMB! MB)
    ) else (
        echo      ℹ  Inno Setup 编译失败或找不到，此步骤跳过（绿色版 ZIP 仍会生成）
    )
) else (
    echo      ℹ  Inno Setup 不可用，跳过安装包生成 (绿色版 ZIP 仍会生成)
)
echo.

REM ------------------------------------------------------------
REM Step 8. 绿色版 ZIP + Setup.exe 一起打包
REM ------------------------------------------------------------
echo [8/9] 生成发布压缩包 (绿色版 + 安装包) + SHA256 校验 ...

set "REL=%ROOT%Release_%VER%"
if exist "%REL%" rd /s /q "%REL%" 2>nul
mkdir "%REL%"

set "ZIP_NAME=FPS_Test_Tool-%VER%-%ARCH%.zip"
set "SETUP_DEST=FPS_Test_Tool_%VER: =%_%ARCH%_Setup.exe"

REM 绿色版 ZIP
echo   ① 绿色免安装版 → %ZIP_NAME%
powershell -NoProfile -Command "Compress-Archive -Force -CompressionLevel Optimal -Path '%OUT%' -DestinationPath '%REL%\%ZIP_NAME%'"

REM 复制 Setup.exe 到 Release
if defined SETUPEXE (
    echo   ② 标准安装包 → %SETUP_DEST%
    copy /y "%SETUPEXE%" "%REL%\%SETUP_DEST%" >nul
    for %%X in ("%REL%\%SETUP_DEST%") do set XS=%%~zX
    set /a XMB=!XS!/1048576
    echo      大小: !XMB! MB
)

REM SHA256
echo   ③ SHA256 校验 ...
pushd "%REL%"
set "SHA=FPS_Test_Tool-%VER%-%ARCH%.sha256.txt"
powershell -NoProfile -Command "$items=@(Get-ChildItem -File -Include *.zip,*.exe); $lines=@(); foreach($f in $items){ $h=Get-FileHash -Algorithm SHA256 -LiteralPath $f.FullName; $lines += \"$($h.Hash)  $($f.Name)\" }; $lines | Out-File -FilePath '%SHA%' -Encoding utf8" 2>nul
if exist "%SHA%" (
    echo      已生成: %SHA%
    echo.
    type "%SHA%"
    echo.
)
popd

REM ------------------------------------------------------------
REM Step 9. 汇总
REM ------------------------------------------------------------
echo [9/9] 完成汇总 ...
echo.
echo ========================================================================
echo   %VER% 构建完成 ✅
echo ========================================================================
echo.
echo   📂 产物目录: %REL%\
echo.
if exist "%REL%\%ZIP_NAME%" (
    for %%Z in ("%REL%\%ZIP_NAME%") do echo      📦 绿色免安装版: %%~nxZ (%%~zZ bytes ~ %%~zZ/1048576 MB)
)
if exist "%REL%\%SETUP_DEST%" (
    echo      💿 标准安装包 (一键安装到桌面/开始菜单/卸载): %SETUP_DEST%
)
echo.
echo   📜 构建日志: %LOG%
echo.
echo   --- 分发使用说明 ---
echo     绿色版 : 解压后双击「%APP_NAME%.exe」即可，无需安装
echo     安装包 : 双击 Setup.exe → 下一步 → 完成（桌面快捷方式 / 开始菜单 / 控制面板卸载）
echo.
echo   📧 反馈邮箱: stardomevision@outlook.com
echo   🐙 GitHub  : https://github.com/stardomevision/FPS_Test_Tool
echo.
pause
