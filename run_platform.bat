@echo off
setlocal
echo ==========================================
echo    STARTING T-HUB SOCIAL PLATFORM
echo ==========================================

:: Change to project directory
cd /d "c:\Users\Kid\Documents\Github\Tech blog"

:: Check if the server is already running? (Optional)
:: For now, just start it in a separate window
echo Starting Local Python Backend...
start "T-Hub Platform Server" cmd /c "C:\Users\Kid\AppData\Local\Programs\Python\Python312\python.exe app.py"

:: Wait for server to boot
timeout /t 3 /nobreak > nul

:: Open the frontend
echo Opening T-Hub Social...
start index.html

echo Platform is now live! 
echo Keep the [T-Hub Platform Server] window open to use Social features.
echo ==========================================
pause
