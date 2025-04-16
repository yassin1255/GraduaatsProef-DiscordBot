@echo off
call .venv\Scripts\activate
start "ModerationBot" cmd /k python ModerationBot.py
start "WelcomeBot" cmd /k python WelcomeBot.py