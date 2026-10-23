@echo off
cd /d "%~dp0"
python verify_release.py
if errorlevel 1 (
 echo Reproduction FAILED.
 exit /b 1
)
echo Reproduction PASSED.
