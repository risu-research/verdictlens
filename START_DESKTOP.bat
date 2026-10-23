@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if %ERRORLEVEL% EQU 0 (start "" pyw -3 "%~dp0VerdictLens_Desktop.pyw" & exit /b 0)
where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (start "" pythonw "%~dp0VerdictLens_Desktop.pyw" & exit /b 0)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (python "%~dp0VerdictLens_Desktop.pyw" & exit /b %ERRORLEVEL%)
echo Python not found. Opening no-install browser edition instead.
start "" "%~dp0VerdictLens_Offline.html"
