@echo off
rem Executa o pipeline manualmente, mostrando o andamento no console.
rem Usa o inicializador "py" (o comando "python" pode abrir a Microsoft Store).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py main.py %*
) else (
    "%LOCALAPPDATA%\Python\bin\python.exe" main.py %*
)
pause
