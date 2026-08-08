@echo off
chcp 65001 >nul
start "" http://127.0.0.1:8899
"C:\Users\21577\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m http.server 8899 --directory "%~dp0web"
