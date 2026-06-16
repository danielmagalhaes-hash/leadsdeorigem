@echo off
cd /d "C:\Users\danie\Downloads\Documentos\leadsdeorigem"

echo [1/2] Gerando dados do dashboard...
venv\Scripts\python.exe scripts\gerar_dashboard_data.py
if errorlevel 1 (
  echo ERRO ao gerar dados. Verifique as credenciais no .env
  pause
  exit /b 1
)

echo.
echo [2/2] Iniciando servidor local na porta 8080...
echo Acesse: http://localhost:8080/leads-crm.html
start "" "http://localhost:8080/leads-crm.html"
venv\Scripts\python.exe -m http.server 8080
