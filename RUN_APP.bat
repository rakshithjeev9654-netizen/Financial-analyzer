@echo off
setlocal
cd /d "%~dp0"
if not exist "app.py" (
  echo ERROR: app.py not found in this folder.
  pause
  exit /b 1
)
if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3 -m venv venv
  if errorlevel 1 python -m venv venv
  if errorlevel 1 (
    echo ERROR: Could not create virtual environment.
    pause
    exit /b 1
  )
)
call "venv\Scripts\activate.bat"
echo Installing/updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Dependency installation failed.
  pause
  exit /b 1
)
if not exist ".env" if exist ".env.example" copy ".env.example" ".env" >nul

echo.
echo Starting Financial Report Analyzer...
echo Open http://127.0.0.1:5000 in your browser.
echo Close this window or press Ctrl+C in it to stop the server.
echo.
python app.py
pause
