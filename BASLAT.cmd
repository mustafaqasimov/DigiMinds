@echo off
setlocal
title DigiMinds - Basladilir
cd /d "%~dp0"

if not exist "tools\start.py" (
  echo XETA: ZIP faylini tam cixardin, sonra BASLAT.cmd faylini acin.
  pause
  exit /b 1
)

echo DigiMinds hazirlanir. Ilk qurasdirma bir nece deqiqe ceke biler.
echo Bu pencereni layiheni istifade etdiyiniz muddetde aciq saxlayin.

py -3.12 -c "import sys; sys.exit(sys.version_info[:2] != (3,12))" >nul 2>&1
if not errorlevel 1 (
  py -3.12 tools\start.py %*
  goto finished
)
py -3 -c "import sys; sys.exit(sys.version_info < (3,12))" >nul 2>&1
if not errorlevel 1 (
  py -3 tools\start.py %*
  goto finished
)
python -c "import sys; sys.exit(sys.version_info < (3,12))" >nul 2>&1
if not errorlevel 1 (
  python tools\start.py %*
  goto finished
)

echo Python 3.12+ tapilmadi. Windows Package Manager ile qurasdirilir.
where winget >nul 2>&1
if errorlevel 1 goto missing_python
winget install --exact --id Python.Python.3.12 --source winget --scope user
if errorlevel 1 goto missing_python
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" tools\start.py %*
  goto finished
)
echo Python qurasdirildi. Bu pencereni baglayib BASLAT.cmd faylini yeniden acin.
pause
exit /b 0

:missing_python
echo Python qurasdirilmadi. https://www.python.org/downloads/windows/ unvanindan qurasdirin.
echo Sonra BASLAT.cmd faylini yeniden acin.
pause
exit /b 1

:finished
set "DIGIMINDS_START_EXIT=%ERRORLEVEL%"
if errorlevel 1 (
  echo.
  echo XETA: Yuxaridaki xeta metnini ve ya bu pencerenin seklini gonderin.
) else (
  echo.
  echo DigiMinds prosesi dayandi. Yeniden acmaq ucun BASLAT.cmd faylini isledin.
)
if /I "%~1"=="--smoke-test" exit /b %DIGIMINDS_START_EXIT%
pause
exit /b %DIGIMINDS_START_EXIT%
