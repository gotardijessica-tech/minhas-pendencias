@echo off
title Instalar Minhas Pendencias
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
echo Terminou. Pode fechar esta janela.
pause >nul
