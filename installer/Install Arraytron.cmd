@echo off
rem Double-click to install or update Arraytron for every Houdini 20.5, 21 and 22 on this PC.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
