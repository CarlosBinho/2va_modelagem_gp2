@echo off
title Exportar figuras do dashboard para o artigo
cd /d "%~dp0.."
set "BASE=%LOCALAPPDATA%"
if not defined BASE set "BASE=%USERPROFILE%\AppData\Local"
set "PY=%BASE%\DashboardDWSNIS\venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Rode primeiro o INICIAR_DASHBOARD.bat uma vez para instalar as bibliotecas.
    pause
    exit /b 1
)
set "DW_FONTE=snapshot"
"%PY%" ferramentas\exportar_figuras_artigo.py
pause
