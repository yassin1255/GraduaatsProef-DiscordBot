@echo off
call .venv\Scripts\activate
start "ModerationBot" cmd /k python ModerationBot.py
start "AiBot" cmd /k python AiBot.py
start "SocialsBot" cmd /k python SocialsBot.py