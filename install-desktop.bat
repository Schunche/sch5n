@echo off
rem Adds Start menu and Desktop shortcuts for the game: double click this file.
rem Run it again after moving the game folder.
setlocal
set "GAME=%~dp0"
powershell -NoProfile -ExecutionPolicy ByPass -Command "$w = New-Object -ComObject WScript.Shell; foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { $s = $w.CreateShortcut((Join-Path $d 'sch5n.lnk')); $s.TargetPath = '%GAME%play.bat'; $s.WorkingDirectory = '%GAME%'; $s.WindowStyle = 7; $s.Save() }"
echo Added sch5n to the Start menu and the Desktop.
