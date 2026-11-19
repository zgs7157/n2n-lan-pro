@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist n2n_pro_manager.exe (
  start "" n2n_pro_manager.exe
) else (
  pythonw n2n_pro_manager.py
)
