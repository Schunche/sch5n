@echo off
rem Removes the game. Double click this file.
rem Deletes your settings, logs and (if you want) your saved worlds, then
rem offers to remove uv and the game folder. It asks before each step.
rem "uninstall.bat --yes" answers yes to everything but removing uv.
setlocal
set "GAME=%~dp0"
if "%GAME:~-1%"=="\" set "GAME=%GAME:~0,-1%"
set "USERDIR=%LOCALAPPDATA%\Schunche\sch5n"
set "YES=0"
if /i "%~1"=="--yes" set "YES=1"

if not exist "%GAME%\data\game.json" goto :not_game
if not exist "%GAME%\play.bat" goto :not_game

echo This removes the game:
echo   your settings and logs  %USERDIR%
echo   your worlds             %USERDIR%\worlds (you will be asked)
echo   the game                %GAME% (you will be asked)
echo Close the game first if it is running.
call :ask "Uninstall the game?" || goto :cancelled

del /q "%USERDIR%\settings.json" "%USERDIR%\logging.json" 2>nul
if exist "%USERDIR%\Logs" rmdir /s /q "%USERDIR%\Logs"
echo Removed your settings and logs.

if not exist "%USERDIR%\worlds" goto :worlds_done
call :ask "Delete your saved worlds too? They cannot be brought back." || goto :keep_worlds
rmdir /s /q "%USERDIR%\worlds"
echo Removed your worlds.
goto :worlds_done
:keep_worlds
echo Kept your worlds in %USERDIR%\worlds
:worlds_done
rmdir "%USERDIR%" 2>nul
rmdir "%LOCALAPPDATA%\Schunche" 2>nul

rem uv may be used by other programs too, so it is only removed when
rem asked, never by --yes.
if "%YES%"=="1" goto :uv_done
where uv >nul 2>nul || goto :uv_done
call :ask "Remove uv and the Python it downloaded? Say no if other programs use uv." || goto :uv_done
uv cache clean
for /f "delims=" %%d in ('uv python dir') do rmdir /s /q "%%d" 2>nul
for /f "delims=" %%d in ('uv tool dir') do rmdir /s /q "%%d" 2>nul
del /q "%USERPROFILE%\.local\bin\uv.exe" "%USERPROFILE%\.local\bin\uvx.exe" "%USERPROFILE%\.local\bin\uvw.exe" 2>nul
echo Removed uv.
:uv_done

call :ask "Delete the game folder %GAME%?" || goto :keep_game
echo Removing the game folder. Goodbye!
if not defined CI pause
cd /d "%TEMP%"
rem Leaving this script first lets it delete its own folder.
(goto) 2>nul & rmdir /s /q "%GAME%"

:keep_game
echo Kept the game folder. Delete it yourself whenever you like.
goto :end

:cancelled
echo Nothing was removed.
goto :end

:not_game
echo This file must stay in the game folder; %GAME% is not one.

:end
if not defined CI pause
exit /b 0

rem ask QUESTION: yes or no, no by default. --yes says yes.
:ask
if "%YES%"=="1" exit /b 0
set "ANSWER="
set /p "ANSWER=%~1 [y/N] "
if /i "%ANSWER%"=="y" exit /b 0
if /i "%ANSWER%"=="yes" exit /b 0
exit /b 1
