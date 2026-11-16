@echo off
setlocal EnableExtensions
title Dashboard DW SNIS - Grupo 2 (UFRPE)
cd /d "%~dp0"
rem Pasta do ambiente Python: fora da pasta compartilhada (nunca vazia)
set "BASE=%LOCALAPPDATA%"
if not defined BASE if defined USERPROFILE set "BASE=%USERPROFILE%\AppData\Local"
if not defined BASE set "BASE=%TEMP%"
if not defined BASE set "BASE=%~dp0"
set "BASE=%BASE%\DashboardDWSNIS"
set "VENV=%BASE%\venv"
set "LOCK=%BASE%\instalando.lock"
set "PORTA=8050"

echo ==============================================================
echo    DASHBOARD DW SNIS - Painel OLAP Financeiro do Saneamento
echo    UFRPE - Modelagem de Dados - 2a VA - Grupo 2
echo ==============================================================
echo.

if not exist "app.py" goto :sem_pasta

rem ---------- 1. Localizar um Python compativel (3.10 a 3.14) ----------
set "PY="
for %%V in (3.12 3.13 3.11 3.10 3.14) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY goto :sem_python

rem ---------- 2. Evitar duas instalacoes ao mesmo tempo (clique duplo repetido) ----------
if not exist "%BASE%" mkdir "%BASE%"
powershell -NoProfile -Command "$p=$env:LOCK; if ((Test-Path $p) -and (((Get-Date)-(Get-Item $p).LastWriteTime).TotalMinutes -lt 15)) { exit 7 }" >nul 2>&1
if "%errorlevel%"=="7" goto :ja_rodando
:continuar
echo instalando > "%LOCK%"

rem ---------- 3. Ambiente virtual (fica fora da pasta compartilhada) ----------
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" -c "import sys" >nul 2>&1 || rmdir /s /q "%VENV%"
)
if not exist "%VENV%\Scripts\python.exe" (
    echo [1/3] Preparando o ambiente Python - so acontece na primeira vez...
    %PY% -m venv "%VENV%"
    if errorlevel 1 goto :erro_venv
)

rem ---------- 4. Bibliotecas: instala so quando o requirements.txt mudar ----------
fc /b "requirements.txt" "%VENV%\requirements_instalado.txt" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Instalando as bibliotecas - na primeira vez pode levar ate 10 minutos.
    echo       Precisa de internet. A tela pode parecer parada em "plotly": e normal.
    echo       Aguarde e NAO feche esta janela...
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip --disable-pip-version-check -q
    "%VENV%\Scripts\python.exe" -m pip install -r requirements.txt --disable-pip-version-check
    if errorlevel 1 goto :erro_pip
    copy /y "requirements.txt" "%VENV%\requirements_instalado.txt" >nul
) else (
    echo [2/3] Bibliotecas ja instaladas.
)
del /q "%LOCK%" >nul 2>&1

rem ---------- 5. Encerrar um dashboard que ja esteja aberto ----------
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORTA% " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

rem ---------- 6. Iniciar ----------
echo [3/3] Iniciando o dashboard. O navegador vai abrir sozinho em alguns segundos.
echo.
echo   Endereco: http://127.0.0.1:%PORTA%
echo   IMPORTANTE: NAO FECHE ESTA JANELA enquanto estiver usando o dashboard.
echo   Para encerrar, feche esta janela.
echo.
set "ABRIR_NAVEGADOR=1"
if not defined DW_FONTE set "DW_FONTE=auto"
"%VENV%\Scripts\python.exe" app.py
echo.
echo O dashboard foi encerrado. Se apareceu algum erro acima, tire um print e envie ao grupo.
pause
exit /b 0

:sem_pasta
echo [ERRO] Este arquivo precisa estar dentro da pasta do dashboard, junto com o app.py.
echo        Se voce abriu direto do arquivo .zip, primeiro clique com o botao direito
echo        no .zip, escolha "Extrair tudo" e rode o INICIAR_DASHBOARD da pasta extraida.
pause
exit /b 1

:sem_python
echo [ERRO] Nao encontrei o Python 3.10 a 3.14 neste computador.
echo.
echo   Como resolver:
echo   1. Na pagina que vai abrir, baixe o "Python 3.12" - Windows installer 64-bit.
echo   2. Na instalacao, MARQUE a caixa "Add python.exe to PATH" e clique em "Install Now".
echo   3. Depois rode este INICIAR_DASHBOARD de novo.
echo.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:ja_rodando
echo O dashboard parece estar sendo preparado em OUTRA janela preta.
echo  - Se ha outra janela aberta: aguarde ela terminar e feche esta.
echo  - Se NAO ha outra janela - voce fechou a anterior no meio - responda S.
echo.
choice /c SN /m "Nao ha outra janela aberta. Continuar mesmo assim"
if errorlevel 2 exit /b 0
del /q "%LOCK%" >nul 2>&1
goto :continuar

:erro_venv
del /q "%LOCK%" >nul 2>&1
echo [ERRO] Nao consegui criar o ambiente Python em:
echo        %VENV%
echo        Reinstale o Python 3.12 marcando "Add python.exe to PATH" e tente de novo.
pause
exit /b 1

:erro_pip
del /q "%VENV%\requirements_instalado.txt" >nul 2>&1
del /q "%LOCK%" >nul 2>&1
echo.
echo [ERRO] A instalacao das bibliotecas falhou.
echo   - Verifique se o computador esta conectado a internet e tente de novo.
echo   - Se continuar, tire um print desta janela e envie ao grupo.
pause
exit /b 1
