@echo off
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver

pause