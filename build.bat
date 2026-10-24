@echo off
rem Builds Sleepify.exe (PyInstaller) and, if Inno Setup is installed, SleepifySetup-x.y.z.exe.
rem Run it from the repository folder:  build.bat
setlocal
cd /d "%~dp0"
set "VER=1.1.0"

echo [1/4] Installing the Python packages...
py -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto :fail

echo [2/4] Making the icons from assets\logo.jpg...
py tools\make_icons.py
if errorlevel 1 goto :fail

echo [3/4] Building Sleepify.exe with PyInstaller...
py -m PyInstaller --noconfirm --clean --onedir --windowed --name Sleepify --icon assets\app.ico --collect-all customtkinter --collect-submodules sleepify --hidden-import pystray._win32 --add-data "assets;assets" Sleepify.py
if errorlevel 1 goto :fail
echo     Done: dist\Sleepify\Sleepify.exe

echo [4/4] Building the installer with Inno Setup...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" goto :noinno
"%ISCC%" /DAppVersion=%VER% "installer\Sleepify.iss"
if errorlevel 1 goto :fail
echo     Done: installer\Output\SleepifySetup-%VER%.exe
goto :end

:noinno
echo     Inno Setup 6 was not found, so no installer was made.
echo     Install it from https://jrsoftware.org/isdl.php and run build.bat again.
goto :end

:fail
echo.
echo Build failed - read the messages above.
exit /b 1

:end
endlocal
