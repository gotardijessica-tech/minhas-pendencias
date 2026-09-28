@echo off
title Desinstalar Minhas Pendencias
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" -Remover
echo.
echo Terminou. Pode fechar esta janela.
pause >nul
