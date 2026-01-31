@echo off
echo ========================================
echo Starting Repo-Copilot System
echo ========================================
echo.

echo [1/2] Starting Backend (FastAPI on port 8000)...
start "Repo-Copilot Backend" cmd /k "cd /d %~dp0 && call D:\LLM\PROJECT\MainProjectVenv\Scripts\activate.bat && python run_backend.py"

timeout /t 3 /nobreak > nul

echo [2/2] Starting Frontend (Streamlit on port 8501)...
start "Repo-Copilot Frontend" cmd /k "cd /d %~dp0 && call D:\LLM\PROJECT\MainProjectVenv\Scripts\activate.bat && python run_frontend.py"

echo.
echo ========================================
echo System Started!
echo ========================================
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Frontend: http://localhost:8501
echo ========================================
echo.
echo Press any key to exit this window (servers will keep running)...
pause > nul
