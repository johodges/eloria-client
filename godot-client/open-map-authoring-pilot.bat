@echo off
setlocal
set "GODOT=C:\Users\User\Desktop\eloria-project\eloria-client\godot-client\Godot_v4.7.2-stable_win64_console.exe"
if not exist "%GODOT%" (
  echo Godot 4.7.2 was not found at:
  echo %GODOT%
  pause
  exit /b 1
)
"%GODOT%" --editor --path "%~dp0." "res://src/dev/map_authoring_pilot/map_authoring_pilot.tscn" %*
