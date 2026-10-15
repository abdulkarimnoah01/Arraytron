@echo off
rem Double-click to remove Arraytron. Your scenes are not touched.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall %*
