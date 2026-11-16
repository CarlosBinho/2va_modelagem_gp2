#!/bin/bash
# Dashboard DW SNIS - iniciador para macOS / Linux (dois cliques no Mac)
cd "$(dirname "$0")" || exit 1
VENV="$HOME/.dashboard_dw_snis/venv"
echo "=============================================================="
echo "   DASHBOARD DW SNIS - Painel OLAP Financeiro do Saneamento"
echo "=============================================================="

PY=""
for v in 3.12 3.13 3.11 3.10 3.14; do
  if command -v "python$v" >/dev/null 2>&1; then PY="python$v"; break; fi
done
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)'; then PY=python3; fi
fi
if [ -z "$PY" ]; then
  echo "[ERRO] Python 3.10 a 3.14 nao encontrado. Instale o Python 3.12 em https://www.python.org/downloads/"
  open "https://www.python.org/downloads/" 2>/dev/null
  read -r -p "Pressione Enter para sair..."; exit 1
fi

if [ -x "$VENV/bin/python" ] && ! "$VENV/bin/python" -c "import sys" >/dev/null 2>&1; then rm -rf "$VENV"; fi
if [ ! -x "$VENV/bin/python" ]; then
  echo "[1/3] Preparando o ambiente Python (so na primeira vez)..."
  mkdir -p "$(dirname "$VENV")" && "$PY" -m venv "$VENV" || { echo "[ERRO] Falha ao criar o ambiente."; read -r -p "Enter para sair..."; exit 1; }
fi

if ! cmp -s requirements.txt "$VENV/requirements_instalado.txt"; then
  echo "[2/3] Instalando as bibliotecas (2 a 5 minutos na primeira vez, precisa de internet)..."
  "$VENV/bin/python" -m pip install --upgrade pip -q --disable-pip-version-check
  if "$VENV/bin/python" -m pip install -r requirements.txt --disable-pip-version-check; then
    cp requirements.txt "$VENV/requirements_instalado.txt"
  else
    echo "[ERRO] Falha na instalacao. Verifique a internet e tente de novo."; read -r -p "Enter para sair..."; exit 1
  fi
else
  echo "[2/3] Bibliotecas ja instaladas."
fi

echo "[3/3] Iniciando... o navegador abre sozinho. NAO feche esta janela enquanto usar o dashboard."
echo "      Endereco: http://127.0.0.1:8050   (para encerrar: Ctrl+C ou feche a janela)"
ABRIR_NAVEGADOR=1 DW_FONTE="${DW_FONTE:-auto}" "$VENV/bin/python" app.py
