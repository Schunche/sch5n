@echo off
rem Starts the game. Double click this file.
rem On the first run it installs uv, which downloads the right Python and
rem everything the game needs. Later runs start straight away.
rem Extra arguments are passed on, e.g. "play.bat edit map1".
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv, the tool that runs the game. This happens only once.
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

uv run --no-dev --python 3.15 sch5n %*
set "result=%errorlevel%"
if not "%result%"=="0" (
    echo.
    echo Something went wrong. See GETTING_STARTED.md, section "Problems".
    if not defined CI pause
)
exit /b %result%
