@echo off
:: Redirect output to update_log.txt for debugging
echo [%date% %time%] Starting blog update... >> update_log.txt

cd /d "c:\Users\Kid\Documents\Github\Tech blog"

:: Run the scraper using the absolute path to Python
"C:\Users\Kid\AppData\Local\Programs\Python\Python312\python.exe" scraper.py >> update_log.txt 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Scraper failed! >> update_log.txt
) else (
    echo [%date% %time%] SUCCESS: Blog updated. >> update_log.txt
)
