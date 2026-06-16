@echo off
cd /d "C:\Users\danie\Downloads\Documentos\leadsdeorigem"
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set dt=%%a
set LOG=logs\cron_%dt:~0,4%-%dt:~4,2%-%dt:~6,2%.log
venv\Scripts\python.exe scripts\cron_daily.py >> "%LOG%" 2>&1
