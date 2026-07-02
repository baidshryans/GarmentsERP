@echo off
env\Scripts\python.exe manage.py migrate
env\Scripts\python.exe manage.py runserver

pause