@echo off

if not exist .\venv (
  virtualenv.exe .\venv
  .\venv\Scripts\pip.exe install -r requirements.txt
)

pause
