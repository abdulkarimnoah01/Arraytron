@echo off
rem Double-click to remove Arraytron Stamp. Your scenes are not touched.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall %*
