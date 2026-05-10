@echo off
setlocal
echo ==========================================
echo    STARTING T-HUB SOCIAL PLATFORM
echo ==========================================

:: Change to project directory
cd /d "c:\Users\Kid\Documents\Github\Tech blog"

:: Install dependencies if needed
echo Checking dependencies...
pip install -r requirements.txt --quiet

:: Optional: Run scraper to get fresh local data
echo Fetching latest news stories...
python scraper.py

echo Starting Local Python Backend...
start "T-Hub Platform Server" cmd /c "python api/index.py"

:: Wait for server to boot
timeout /t 5 /nobreak > nul

:: Open the frontend via the local server
echo Opening T-Hub Social...
start http://localhost:5000

echo Platform is now live at http://localhost:5000! 
echo ==========================================
pause
