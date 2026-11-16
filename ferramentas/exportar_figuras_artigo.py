"""
Exporta, em PNG, os gráficos do dashboard usados nas análises OLAP do artigo da 2ª VA.

Os gráficos são gerados pelas PRÓPRIAS funções de callback do app.py (Plotly Dash), com os
mesmos filtros descritos em cada análise do artigo. Um navegador renderiza cada figura com o
Plotly.js e devolve a imagem, que é salva em  dashboard/figuras_artigo/.

Uso (Windows): dois cliques em ferramentas/GERAR_FIGURAS_ARTIGO.bat
"""
import base64
import json
import os
import sys
import threading
import webbrowser

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
os.environ.setdefault("DW_FONTE", "snapshot")

import plotly  # noqa: E402
from flask import Flask, Response, request  # noqa: E402

import app as painel  # noqa: E402  (o próprio dashboard)

SAIDA = os.path.join(RAIZ, "figuras_artigo")
os.makedirs(SAIDA, exist_ok=True)
D = painel.DADOS
TODAS_UFS = sorted(D.dim_localidade.sigla_uf.unique())


def filtros(aba, anos=(1995, 2022), regioes=None, escala="1e9"):
    regioes = regioes or list(D.regioes)
    ufs = sorted(u for r in regioes for u in D.uf_por_regiao.get(r, []))
    return [list(anos), [], "TODOS", "TODOS", regioes, ufs,
            list(D.dim_esfera.codigo_esfera), list(D.dim_porte.codigo_porte),
            list(D.dim_faixa.codigo_faixa), escala, 0, aba]


def figuras():
    figs = {}
    # Análise 1 — evolução nacional 1995-2022 (Visão Executiva)
    r = painel.atualizar_executiva(*filtros("exec"), "receita_operacional")
    figs["A1_evolucao_receita_despesa_investimento"] = (r[1], 1100, 460)
    # Análise 2 — receita por UF e região, 2018-2022 (Visão Executiva)
    r = painel.atualizar_executiva(*filtros("exec", (2018, 2022)), "receita_operacional")
    figs["A2_receita_por_uf_2018_2022"] = (r[3], 1100, 420)
    # Análise 3 — composição da despesa, Nordeste 2022 (Composição)
    r = painel.atualizar_composicao(*filtros("comp", (2022, 2022), ["Nordeste"], "1e6"), "DESPESAS",
                                    "despesa_total_servico")
    figs["A3_composicao_despesas_nordeste_2022"] = (r[0], 1100, 520)
    # Análise 4 — investimento por esfera e origem, 2010-2022 (Investimentos)
    r = painel.atualizar_investimentos(*filtros("inv", (2010, 2022)))
    figs["A4_investimento_por_esfera_2010_2022"] = (r[0], 1000, 420)
    figs["A4_origem_dos_recursos_2010_2022"] = (r[1], 700, 420)
    # Análise 5 — Marco Legal, janelas 2017-2019 x 2020-2022 (Investimentos)
    r = painel.atualizar_investimentos(*filtros("inv", (2017, 2022)))
    figs["A5_marco_legal_por_regiao"] = (r[3], 1000, 420)
    # Análise 6 — porte do município, 2018-2022 (Porte & Faixa)
    r = painel.atualizar_segmentos(*filtros("seg", (2018, 2022)))
    figs["A6_financas_por_porte_2018_2022"] = (r[0], 1000, 420)
    # Análise 7 — porte x faixa de valor e qualidade das declarações (Porte & Faixa)
    r = painel.atualizar_segmentos(*filtros("seg"))
    figs["A7_matriz_porte_faixa"] = (r[2], 1000, 420)
    figs["A7_qualidade_declaracoes"] = (r[3], 1000, 420)
    # Análise 8 — Top 15 municípios do Nordeste em investimento, 2020-2022 (Territorial)
    r = painel.atualizar_territorial(*filtros("ter", (2020, 2022), ["Nordeste"], "1e6"),
                                     "investimento_total", 15, [-100, 100])
    figs["A8_ranking_investimento_nordeste_2020_2022"] = (r[1], 1000, 560)
    return figs


FIGS = figuras()
servidor = Flask(__name__)
PLOTLY_JS = os.path.join(os.path.dirname(plotly.__file__), "package_data", "plotly.min.js")


@servidor.route("/plotly.min.js")
def plotly_js():
    return Response(open(PLOTLY_JS, "rb").read(), mimetype="application/javascript")


@servidor.route("/")
def pagina():
    dados = {n: {"fig": json.loads(f.to_json()), "w": w, "h": h} for n, (f, w, h) in FIGS.items()}
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Exportando figuras</title>
<script src="/plotly.min.js"></script></head>
<body style="font-family:Segoe UI,sans-serif;padding:24px">
<h2>Exportando os gráficos do dashboard para o artigo...</h2><ol id="log"></ol>
<div id="area" style="position:absolute;left:-5000px"></div>
<script>
const FIGS = {json.dumps(dados)};
(async () => {{
  const log = document.getElementById('log'); let ok = 0;
  for (const [nome, item] of Object.entries(FIGS)) {{
    const div = document.createElement('div'); document.getElementById('area').appendChild(div);
    const layout = Object.assign({{}}, item.fig.layout, {{width: item.w, height: item.h}});
    await Plotly.newPlot(div, item.fig.data, layout, {{staticPlot: true}});
    const url = await Plotly.toImage(div, {{format: 'png', width: item.w, height: item.h, scale: 2}});
    const r = await fetch('/salvar/' + nome, {{method: 'POST', body: url}});
    const li = document.createElement('li'); li.textContent = nome + (r.ok ? ' ✔' : ' ✘'); log.appendChild(li);
    if (r.ok) ok++;
  }}
  const fim = document.createElement('h3');
  fim.textContent = ok + ' de ' + Object.keys(FIGS).length + ' figuras salvas em dashboard/figuras_artigo. Pode fechar esta aba.';
  document.body.appendChild(fim); fetch('/fim', {{method: 'POST'}});
}})();
</script></body></html>"""


@servidor.route("/salvar/<nome>", methods=["POST"])
def salvar(nome):
    if nome not in FIGS:
        return "nome inválido", 400
    b64 = request.get_data(as_text=True).split(",", 1)[1]
    with open(os.path.join(SAIDA, f"{nome}.png"), "wb") as fh:
        fh.write(base64.b64decode(b64))
    print(f"  salvo: figuras_artigo/{nome}.png")
    return "ok"


@servidor.route("/fim", methods=["POST"])
def fim():
    print("\nConcluído. As figuras estão em dashboard/figuras_artigo. Pode fechar esta janela.")
    return "ok"


if __name__ == "__main__":
    porta = 8051
    print(f"Gerando {len(FIGS)} figuras do dashboard para o artigo...")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{porta}/")).start()
    servidor.run(host="127.0.0.1", port=porta, debug=False)
