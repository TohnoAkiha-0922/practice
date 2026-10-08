@echo off
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" server.py > server.out.log 2> server.err.log
