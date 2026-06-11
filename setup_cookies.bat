@echo off
chcp 65001 >nul
echo ==========================================
echo   舆情爬虫 - Cookie自动提取工具
echo ============================================
echo.
echo 此脚本将自动:
echo   1. 启动专用Chrome（调试端口9222）
echo   2. 打开黑猫投诉和小红书登录页
echo   3. 等待你手动登录
echo   4. 自动提取Cookie到chrome_profile目录
echo.
echo 重要: 请用同一Chrome窗口登录两个网站！
echo.
pause

:: 获取Chrome路径
for /f "tokens=2*" %%i in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /v Path 2^>nul') do set CHROME_DIR=%%j
set CHROME_EXE=%CHROME_DIR%\Chrome\Application\chrome.exe
if not exist "%CHROME_EXE%" set CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe

:: 获取本机用户名
set USERNAME=%USERNAME%

:: Chrome默认Profile路径
set DEFAULT_PROFILE=%LOCALAPPDATA%\Google\Chrome\User Data\Default

:: 清理旧的调试Chrome进程
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul

:: 启动专用Chrome（独立Profile + 调试端口）
echo.
echo 正在启动Chrome...
start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%CD%\chrome_profile" https://tousu.sina.com.cn/ https://www.xiaohongshu.com

echo.
echo 请在新打开的Chrome窗口中:
echo   1. 登录黑猫投诉: https://tousu.sina.com.cn
echo   2. 登录小红书: https://www.xiaohongshu.com
echo.
echo 登录完成后按任意键继续...
pause >nul

:: 复制Cookie文件
echo.
echo 正在提取Cookie...

:: 关闭Chrome以便复制文件
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul

:: 复制Network/Cookies
if exist "%DEFAULT_PROFILE%\Network\Cookies" (
    mkdir "%CD%\chrome_profile\Network" 2>nul
    copy /Y "%DEFAULT_PROFILE%\Network\Cookies" "%CD%\chrome_profile\Network\Cookies"
    echo   Cookies复制成功
)

:: 复制Preferences
if exist "%DEFAULT_PROFILE%\Preferences" (
    copy /Y "%DEFAULT_PROFILE%\Preferences" "%CD%\chrome_profile\Preferences"
    echo   Preferences复制成功
)

echo.
echo ==========================================
echo   Cookie提取完成!
echo ==========================================
echo.
echo 下一步: 启动爬虫
echo   python crawler_web.py
echo.
pause
