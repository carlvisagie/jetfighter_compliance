@echo off
echo =============================================
echo 🚀 LAUNCHING COMPLIANCE ENGINE (VISIBLE MODE)
echo =============================================

set PYTHON="E:\JetFighter_Compliance\.venv\Scripts\python.exe"
set SERVER="E:\JetFighter_Compliance\server.py"

echo Starting FastAPI server...
%PYTHON% %SERVER%

echo.
echo ✅ Compliance engine stopped or exited.
pause
