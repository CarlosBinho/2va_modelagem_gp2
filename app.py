"""
=====================================================================================
 DW SNIS — Painel OLAP Financeiro do Saneamento (Plotly Dash)
 UFRPE / DEINFO — Modelagem de Dados — 2ª VA — Grupo 2
 Data Warehouse: dw_snis_financeiro  (Estrela Única: 1 fato + 6 dimensões)
-------------------------------------------------------------------------------------
 Fato:     fato_financeiro_anual  (grão: município × ano × componente × esfera)
 Dimensões: dim_tempo, dim_localidade, dim_componente, dim_esfera,
            dim_porte_municipio, dim_faixa_valor
-------------------------------------------------------------------------------------
 Executar:  python app.py   (ou F5 no VS Code)  ->  http://127.0.0.1:8050
=====================================================================================
"""
import io
import math
import os
import threading
from collections import OrderedDict
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Group, Scheme, Symbol

from dw_dados import carregar_dados

# =====================================================================================
# 1. CARGA DO DATA WAREHOUSE (MySQL -> fallback snapshot)
# =====================================================================================
DADOS = carregar_dados()

# Rubricas de referência usadas nos indicadores (nunca somadas entre si -> sem dupla contagem)
C_RECEITA = "receita_operacional"
C_DESPESA = "despesa_total_servico"
C_INVEST = "investimento_total"
C_ARRECAD = "arrecadacao_total"
C_CREDITO = "credito_a_receber"
C_DEX = "despesa_exploracao"

DESTINOS_INV = ["investimento_agua", "investimento_esgoto", "investimento_outro"]
ORIGENS_INV = ["investimento_recurso_proprio", "investimento_recurso_oneroso",
               "investimento_recurso_nao_oneroso"]
ESFERAS_INV = ["PRESTADOR", "MUNICIPIO", "ESTADO"]
ESFERAS_NOMES = ["Prestador de serviços", "Município", "Estado", "Não se aplica"]
NOMES_CURTOS_INV = {
    "investimento_recurso_proprio": "Recursos próprios",
    "investimento_recurso_oneroso": "Recursos onerosos",
    "investimento_recurso_nao_oneroso": "Recursos não onerosos",
    "investimento_agua": "Água", "investimento_esgoto": "Esgoto", "investimento_outro": "Outros",
}
FAIXA_CURTA = {"VALOR_NEGATIVO": "Negativo", "VALOR_ZERADO": "Zero",
               "FAIXA_ATE_100K": "Até 100 mil", "FAIXA_100K_1M": "100 mil – 1 mi",
               "FAIXA_1M_10M": "1 mi – 10 mi", "FAIXA_ACIMA_10M": "Acima de 10 mi"}
CORES_RUBRICA = {"Receita operacional total": "#2563eb", "Despesa total dos serviços": "#f97316",
                 "Investimento total": "#7c3aed"}

CORES_REGIAO = {"Norte": "#0f9d8a", "Nordeste": "#e8833a", "Centro-Oeste": "#c8a415",
                "Sudeste": "#3b6fd8", "Sul": "#8b5cf6"}
CORES_ESFERA = {"Prestador de serviços": "#2563eb", "Município": "#0d9488", "Estado": "#d97706",
                "Não se aplica": "#94a3b8"}
CORES_PERIODO = {"Pré-Marco Legal (até 2019)": "#94a3b8", "Pós-Marco Legal (2020+)": "#0d9488"}

# Classificação das parcelas declaradas (evita somar classificações cruzadas)
CLASSE_RUBRICA = {
    "receita_operacional_direta_agua": "Receita direta",
    "receita_operacional_direta_esgoto": "Receita direta",
    "receita_operacional_indireta": "Receita indireta",
    "receita_operacional_direta_agua_exportada": "Intercâmbio (já contido na direta)",
    "receita_operacional_direta_esgoto_importado": "Intercâmbio (já contido na direta)",
    "despesa_pessoal": "Compõe a DEX", "despesa_energia": "Compõe a DEX",
    "despesa_produto_quimico": "Compõe a DEX", "despesa_servico_terceiro": "Compõe a DEX",
    "despesa_agua_importada": "Compõe a DEX", "despesa_esgoto_exportado": "Compõe a DEX",
    "despesa_fiscal": "Compõe a DEX", "despesa_exploracao_outro": "Compõe a DEX",
    "despesa_ativo": "Fora da DEX (compõe a DTS)",
    "despesa_fiscal_nao_computada": "Fora da DEX (compõe a DTS)",
    "despesa_servico_outro": "Fora da DEX (compõe a DTS)",
    "investimento_agua": "Destino do investimento", "investimento_esgoto": "Destino do investimento",
    "investimento_outro": "Destino do investimento",
    "investimento_recurso_proprio": "Origem do recurso",
    "investimento_recurso_oneroso": "Origem do recurso",
    "investimento_recurso_nao_oneroso": "Origem do recurso",
    "despesa_capitalizavel": "Despesa capitalizável",
}
CORES_CLASSE = {
    "Receita direta": "#2563eb", "Receita indireta": "#60a5fa",
    "Intercâmbio (já contido na direta)": "#cbd5e1",
    "Compõe a DEX": "#f97316", "Fora da DEX (compõe a DTS)": "#fdba74",
    "Destino do investimento": "#0d9488", "Origem do recurso": "#7c3aed",
    "Despesa capitalizável": "#94a3b8",
}
REFERENCIA_GRUPO = {"RECEITAS": "receita_operacional", "DESPESAS": "despesa_total_servico",
                    "INVESTIMENTOS": "investimento_total"}

ESCALAS = {"1e3": ("R$ mil", 1e3), "1e6": ("R$ milhões", 1e6), "1e9": ("R$ bilhões", 1e9)}

PLANSAB_OPCOES = [{"label": "Todos", "value": "TODOS"},
                  {"label": "Pré-PLANSAB (até 2013)", "value": "PRE_PLANSAB"},
                  {"label": "Vigência PLANSAB (2014+)", "value": "VIGENCIA_PLANSAB"}]
MARCO_OPCOES = [{"label": "Todos", "value": "TODOS"},
                {"label": "Pré-Marco Legal (até 2019)", "value": "PRE_MARCO_LEGAL"},
                {"label": "Pós-Marco Legal (2020+)", "value": "POS_MARCO_LEGAL"}]


# =====================================================================================
# 2. FUNÇÕES AUXILIARES (formatação pt-BR, filtros OLAP, figuras)
# =====================================================================================
def num_br(v, casas=2):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v, casas=2):
    return ("-" if v < 0 else "") + "R$ " + num_br(abs(v), casas)


def brl_curto(v):
    a = abs(v)
    sinal = "-" if v < 0 else ""
    if a >= 1e9:
        return f"{sinal}R$ {num_br(a / 1e9)} bi"
    if a >= 1e6:
        return f"{sinal}R$ {num_br(a / 1e6)} mi"
    if a >= 1e3:
        return f"{sinal}R$ {num_br(a / 1e3)} mil"
    return f"{sinal}R$ {num_br(a)}"


def pct(v, casas=1):
    return "—" if v is None or pd.isna(v) else f"{num_br(v * 100, casas)}%"


def razao(a, b):
    return a / b if b else None


def filtros_padrao():
    return {
        "anos": [DADOS.ano_min, DADOS.ano_max], "decadas": [], "plansab": "TODOS",
        "marco": "TODOS", "regioes": list(DADOS.regioes),
        "ufs": sorted(DADOS.dim_localidade.sigla_uf.unique()),
        "esferas": list(DADOS.dim_esfera.codigo_esfera),
        "portes": list(DADOS.dim_porte.codigo_porte),
        "faixas": list(DADOS.dim_faixa.codigo_faixa), "escala": "1e6",
    }


def montar_filtros(anos, decadas, plansab, marco, regioes, ufs, esferas, portes, faixas, escala):
    return {"anos": anos or [DADOS.ano_min, DADOS.ano_max], "decadas": decadas or [],
            "plansab": plansab or "TODOS", "marco": marco or "TODOS", "regioes": regioes or [],
            "ufs": ufs or [], "esferas": esferas or [], "portes": portes or [],
            "faixas": faixas or [], "escala": escala or "1e6"}


_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()


def aplicar_filtros(df, f):
    """SLICE & DICE com cache: vários callbacks pedem o mesmo recorte na mesma interação.
    O DataFrame devolvido é compartilhado: quem precisar alterá-lo deve usar .copy()."""
    chave = (id(df), tuple(f["anos"]), tuple(f["decadas"]), f["plansab"], f["marco"],
             tuple(f["regioes"]), tuple(sorted(f["ufs"])), tuple(sorted(f["esferas"])),
             tuple(sorted(f["portes"])), tuple(sorted(f["faixas"])))
    with _CACHE_LOCK:
        if chave in _CACHE:
            _CACHE.move_to_end(chave)
            return _CACHE[chave]
    res = _filtrar(df, f)
    with _CACHE_LOCK:
        _CACHE[chave] = res
        while len(_CACHE) > 16:
            _CACHE.popitem(last=False)
    return res


def _filtrar(df, f):
    """Aplica os recortes das 6 dimensões sobre um cubo."""
    m = df["ano"].between(f["anos"][0], f["anos"][1])
    if f["decadas"]:
        m &= df["decada"].isin(f["decadas"])
    if f["plansab"] != "TODOS":
        m &= df["periodo_plansab"] == f["plansab"]
    if f["marco"] != "TODOS":
        m &= df["periodo_marco_legal"] == f["marco"]
    if f["regioes"]:
        m &= df["nome_regiao"].isin(f["regioes"])
    # Checkboxes de UF: se todas forem desmarcadas, o resultado é vazio (regra do slide 22)
    m &= df["sigla_uf"].isin(f["ufs"])
    m &= df["esfera"].isin(f["esferas"])
    m &= df["porte"].isin(f["portes"])
    m &= df["faixa"].isin(f["faixas"])
    return df[m]


def soma(df, componente, col="valor_informado_rs"):
    return float(df.loc[df["componente"] == componente, col].sum())


def saldo_ultimo_ano(df, componente):
    """Semi-aditividade: saldo (credito_a_receber) nunca é somado entre anos."""
    d = df[df["componente"] == componente]
    if d.empty:
        return 0.0, None
    ano = int(d["ano"].max())
    return float(d.loc[d["ano"] == ano, "valor_informado_rs"].sum()), ano


def variacao_anual(df, componente):
    """Variação nominal do último ano do recorte sobre o ano anterior."""
    d = df[df["componente"] == componente]
    if d.empty:
        return "Sem dados no recorte"
    serie = d.groupby("ano", observed=True)["valor_informado_rs"].sum().sort_index()
    if len(serie) < 2 or serie.index[-1] - serie.index[-2] != 1 or not serie.iloc[-2]:
        return f"Recorte: {brl(serie.sum(), 0)}"
    v = serie.iloc[-1] / serie.iloc[-2] - 1
    seta = "▲" if v >= 0 else "▼"
    return f"{seta} {num_br(abs(v) * 100, 1)}% em {serie.index[-1]} vs {serie.index[-2]}"


def respeitar_regra_temporal(df, componente):
    if DADOS.regra_temporal.get(componente) == "NAO_SOMAR_ANOS" and not df.empty:
        return df[df["ano"] == df["ano"].max()], True
    return df, False


def txt(df):
    """Converte colunas categóricas em texto (evita categorias vazias nos gráficos)."""
    df = df.copy()
    for c in df.select_dtypes("category").columns:
        df[c] = df[c].astype(str)
    return df


def figura_vazia(msg="Nenhum dado para os filtros selecionados"):
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                       font={"size": 14, "color": "#64748b"})
    fig.update_layout(template="plotly_white", xaxis={"visible": False},
                      yaxis={"visible": False}, height=380, margin=dict(l=20, r=20, t=20, b=20))
    return fig


def estilo(fig, altura=420, legenda_h=True):
    fig.update_layout(
        template="plotly_white", height=altura, separators=",.",
        font={"family": "Inter, Segoe UI, sans-serif", "size": 12, "color": "#1e293b"},
        margin=dict(l=10, r=10, t=30, b=10), hoverlabel={"font": {"size": 12}},
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
        if legenda_h else {},
    )
    # Sem sufixos SI (k, M, G) nos eixos: valores sempre na escala escolhida, com milhar "."
    fig.update_xaxes(exponentformat="none", separatethousands=True)
    fig.update_yaxes(exponentformat="none", separatethousands=True)
    return fig


def eixo_anos(fig, n_anos=28):
    """Eixo temporal: anos inteiros sem separador de milhar."""
    fig.update_xaxes(tickformat="d", dtick=1 if n_anos <= 12 else 2, tickangle=-45)
    return fig


def rotulo_escala(f):
    return ESCALAS[f["escala"]][0]


def div_escala(f):
    return ESCALAS[f["escala"]][1]


def nome_periodo_marco(v):
    return "Pós-Marco Legal (2020+)" if v == "POS_MARCO_LEGAL" else "Pré-Marco Legal (até 2019)"


# =====================================================================================
# 3. COMPONENTES DE LAYOUT
# =====================================================================================
def titulo_card(icone, texto, sub=None):
    return html.Div(className="card-titulo", children=[
        html.H3([html.Span(icone, className="ico"), texto]),
        html.P(sub, className="card-sub") if sub else None,
    ])


def grafico(id_, altura=None):
    return dcc.Loading(type="dot", color="#0d9488", children=dcc.Graph(
        id=id_, config={"displaylogo": False, "locale": "pt-BR",
                        "toImageButtonOptions": {"format": "png", "scale": 2, "filename": id_}},
        style={"height": f"{altura}px"} if altura else None))


def bloco_filtro(icone, titulo, conteudo, ajuda=None, extra=None):
    return html.Div(className="filtro-bloco", children=[
        html.Div(className="filtro-cab", children=[
            html.Label([html.Span(icone, className="ico"), titulo]), extra]),
        conteudo,
        html.Small(ajuda, className="filtro-ajuda") if ajuda else None,
    ])


def painel_filtros():
    p = filtros_padrao()
    marcas = {a: str(a) for a in range(DADOS.ano_min, DADOS.ano_max + 1)
              if a == DADOS.ano_min or (a % 5 == 0 and DADOS.ano_max - a >= 3)}
    marcas[DADOS.ano_max] = str(DADOS.ano_max)
    return html.Aside(className="sidebar", children=[
        html.H2([html.Span("🎯", className="ico"), "Filtros Multidimensionais"]),
        html.P("Cada controle corresponde a uma dimensão da estrela dw_snis_financeiro.",
               className="sidebar-sub"),

        bloco_filtro("📅", "Dimensão Tempo — Período (ano)", dcc.RangeSlider(
            id="f-anos", min=DADOS.ano_min, max=DADOS.ano_max, step=1, value=p["anos"],
            marks=marcas, allowCross=False,
            tooltip={"placement": "bottom", "always_visible": False}),
            "O SNIS é declarado anualmente: o grão de dim_tempo é o ano (sem meses fictícios)."),
        bloco_filtro("🗓️", "Dimensão Tempo — Década", dcc.Dropdown(
            id="f-decada", multi=True, placeholder="Todas as décadas",
            options=[{"label": f"Década de {d}", "value": d}
                     for d in sorted(DADOS.dim_tempo.decada.unique())])),
        bloco_filtro("📜", "Período PLANSAB (Portaria 571/2013)", dcc.RadioItems(
            id="f-plansab", options=PLANSAB_OPCOES, value="TODOS", className="radio-col")),
        bloco_filtro("⚖️", "Novo Marco Legal (Lei 14.026/2020)", dcc.RadioItems(
            id="f-marco", options=MARCO_OPCOES, value="TODOS", className="radio-col")),

        html.Hr(),
        bloco_filtro("📍", "Dimensão Localidade — Região", dcc.Dropdown(
            id="f-regiao", multi=True, value=p["regioes"],
            options=[{"label": r, "value": r} for r in DADOS.regioes],
            placeholder="Selecione regiões")),
        html.Div(className="uf-box", children=[
            html.Div(className="uf-cab", children=[
                html.Strong("🗺️ Estados da Federação (UF)"),
                html.Span(id="badge-ufs", className="badge")]),
            html.Div(className="uf-acoes", children=[
                html.Button("Marcar todos", id="btn-uf-todos", className="btn-link"),
                html.Button("Limpar", id="btn-uf-limpar", className="btn-link")]),
            html.Small("Hierarquia Região ➔ UF (callback em cascata). Ao escolher regiões, "
                       "todas as UFs correspondentes iniciam marcadas.", className="filtro-ajuda"),
            dcc.Checklist(id="f-uf", options=[], value=p["ufs"], className="uf-grid",
                          inputClassName="chk", labelClassName="uf-item"),
        ]),

        html.Hr(),
        bloco_filtro("🏛️", "Dimensão Esfera", dcc.Checklist(
            id="f-esfera", value=p["esferas"], className="chk-col", inputClassName="chk",
            options=[{"label": r.nome_esfera, "value": r.codigo_esfera}
                     for r in DADOS.dim_esfera.itertuples()]),
            "Receitas, despesas e créditos usam o membro “Não se aplica”; "
            "investimentos se dividem em Prestador, Município e Estado."),
        bloco_filtro("🏙️", "Dimensão Porte do Município", dcc.Checklist(
            id="f-porte", value=p["portes"], className="chk-col", inputClassName="chk",
            options=[{"label": r.nome_porte, "value": r.codigo_porte}
                     for r in DADOS.dim_porte.itertuples()]),
            "Classificação pela população urbana declarada no ano."),
        bloco_filtro("💰", "Dimensão Faixa de Valor", dcc.Checklist(
            id="f-faixa", value=p["faixas"], className="chk-col", inputClassName="chk",
            options=[{"label": r.nome_faixa, "value": r.codigo_faixa}
                     for r in DADOS.dim_faixa.itertuples()]),
            "6 faixas contínuas e sem lacunas do montante declarado."),

        html.Hr(),
        bloco_filtro("📐", "Escala dos gráficos", dcc.RadioItems(
            id="f-escala", value="1e6", className="radio-row",
            options=[{"label": v[0], "value": k} for k, v in ESCALAS.items()])),
        html.Button("↺ Redefinir todos os filtros", id="btn-reset", className="btn-reset"),
    ])


def aba_executiva():
    return html.Div(children=[
        html.Div(id="kpis", className="kpi-grid"),
        html.Div(className="linha", children=[
            html.Div(className="card col-8", children=[
                titulo_card("📈", "Evolução Temporal: Receita, Despesa, Resultado e Investimento",
                            "Barras = receita operacional total e despesa total dos serviços; "
                            "linhas = resultado (receita − despesa) e investimento total"),
                grafico("fig-evolucao")]),
            html.Div(className="card col-4", children=[
                titulo_card("🧭", "Desempenho por Região Geográfica",
                            "Roll-up de dim_localidade (Município ➔ UF ➔ Região)"),
                html.Div(id="cards-regiao", className="regiao-grid")]),
        ]),
        html.Div(className="card", children=[
            html.Div(className="card-cab-flex", children=[
                titulo_card("🗺️", "Desempenho Regional por Estado e Região",
                            "Barras agrupadas: UFs dentro de cada macrorregião"),
                dcc.RadioItems(id="sel-metrica-uf", value=C_RECEITA, className="seg",
                               options=[{"label": "Receita", "value": C_RECEITA},
                                        {"label": "Despesa", "value": C_DESPESA},
                                        {"label": "Investimento", "value": C_INVEST},
                                        {"label": "Arrecadação", "value": C_ARRECAD}])]),
            grafico("fig-uf")]),
    ])


def aba_composicao():
    opcoes_rubrica = [{"label": f"{r.nome_componente}  ·  {r.grupo_financeiro.title()}",
                       "value": r.codigo_componente} for r in DADOS.dim_componente.itertuples()]
    return html.Div(children=[
        html.Div(className="card", children=[
            html.Div(className="card-cab-flex", children=[
                titulo_card("🧩", "Composição Financeira por Rubrica (dim_componente)",
                            "Somente rubricas declaradas (parcelas). Totais e subtotais são "
                            "referências e não são somados às parcelas — evita dupla contagem."),
                dcc.RadioItems(id="sel-grupo", value="DESPESAS", className="seg",
                               options=[{"label": "Receitas", "value": "RECEITAS"},
                                        {"label": "Despesas", "value": "DESPESAS"},
                                        {"label": "Investimentos", "value": "INVESTIMENTOS"}])]),
            grafico("fig-composicao")]),
        html.Div(className="card", children=[
            html.Div(className="card-cab-flex", children=[
                titulo_card("🔎", "Drill-down de uma Rubrica",
                            "Escolha qualquer uma das 30 rubricas da dimensão componente"),
                html.Div(className="sel-largo", children=dcc.Dropdown(
                    id="sel-rubrica", value=C_RECEITA, clearable=False, options=opcoes_rubrica))]),
            html.Div(id="nota-rubrica", className="nota"),
            html.Div(className="linha", children=[
                html.Div(className="col-6", children=[
                    html.H4("Treemap Região ➔ UF", className="sub-h"), grafico("fig-treemap")]),
                html.Div(className="col-6", children=[
                    html.H4("Matriz Região × Ano (participação % no total de cada ano)", className="sub-h"), grafico("fig-heatmap")]),
            ]),
        ]),
    ])


def aba_investimentos():
    return html.Div(children=[
        html.Div(className="linha", children=[
            html.Div(className="card col-7", children=[
                titulo_card("🏗️", "Investimento Total por Esfera ao Longo do Tempo",
                            "Rubrica investimento_total aberta por dim_esfera (barras empilhadas)"),
                grafico("fig-inv-esfera")]),
            html.Div(className="card col-5", children=[
                titulo_card("🥧", "Origem dos Recursos Investidos",
                            "Próprios × onerosos × não onerosos"),
                grafico("fig-inv-origem")]),
        ]),
        html.Div(className="linha", children=[
            html.Div(className="card col-6", children=[
                titulo_card("💧", "Destino do Investimento por Esfera",
                            "Água × Esgoto × Outros. Destino e origem são classificações "
                            "cruzadas do mesmo investimento: não devem ser somadas."),
                grafico("fig-inv-destino")]),
            html.Div(className="card col-6", children=[
                titulo_card("⚖️", "Novo Marco Legal: Investimento Médio Anual por Região",
                            "Janelas de mesma duração antes e depois da Lei 14.026/2020 "
                            "(valores nominais)"),
                grafico("fig-inv-marco")]),
        ]),
    ])


def aba_segmentos():
    return html.Div(children=[
        html.Div(className="linha", children=[
            html.Div(className="card col-6", children=[
                titulo_card("🏙️", "Finanças por Porte do Município (dim_porte_municipio)",
                            "Receita, despesa e investimento por classe demográfica"),
                grafico("fig-porte")]),
            html.Div(className="card col-6", children=[
                titulo_card("📊", "Distribuição por Faixa de Valor (dim_faixa_valor)",
                            "Quantidade de declarações (SUM quantidade_registros) por faixa"),
                grafico("fig-faixa")]),
        ]),
        html.Div(className="linha", children=[
            html.Div(className="card col-6", children=[
                titulo_card("🔥", "Matriz Porte × Faixa de Valor",
                            "Cruzamento de duas dimensões de segmentação (contagem de declarações)"),
                grafico("fig-porte-faixa")]),
            html.Div(className="card col-6", children=[
                titulo_card("✅", "Qualidade das Declarações ao Longo do Tempo",
                            "Barras = declarações informadas; linha = % com valor positivo"),
                grafico("fig-positivos")]),
        ]),
    ])


def aba_territorial():
    opcoes = [{"label": DADOS.nome_componente.get(c, c), "value": c}
              for c in (C_RECEITA, C_DESPESA, C_DEX, C_INVEST, C_ARRECAD, C_CREDITO)]
    return html.Div(children=[
        html.Div(className="card", children=[
            html.Div(className="card-cab-flex", children=[
                titulo_card("🌎", "Mapa dos Municípios", "Drill-down até o grão municipal"),
                html.Div(className="sel-largo", children=dcc.Dropdown(
                    id="sel-rubrica-mun", value=C_INVEST, clearable=False, options=opcoes))]),
            html.Div(className="linha", children=[
                html.Div(className="col-7", children=[grafico("fig-mapa")]),
                html.Div(className="col-5", children=[
                    html.Div(className="topn", children=[
                        html.Span("Top N municípios:"),
                        dcc.Slider(id="sel-topn", min=5, max=30, step=5, value=15,
                                   marks={i: str(i) for i in range(5, 31, 5)})]),
                    grafico("fig-ranking")]),
            ]),
        ]),
        html.Div(className="card", children=[
            html.Div(className="card-cab-flex", children=[
                titulo_card("🎯", "Dispersão Multivariada: Receita × Margem Operacional por Município",
                            "Eixo X = receita operacional (escala log), Eixo Y = margem "
                            "(receita − despesa)/receita, tamanho = investimento total, "
                            "cor = região. Amostra: 600 maiores receitas do recorte."),
                html.Div(className="slider-metrica", children=[
                    html.Label("Faixa de margem operacional (%)"),
                    dcc.RangeSlider(id="sel-margem", min=-100, max=100, step=5, value=[-100, 100],
                                    marks={v: f"{v}%" for v in (-100, -50, 0, 50, 100)},
                                    allowCross=False,
                                    tooltip={"placement": "bottom", "always_visible": False})])]),
            grafico("fig-dispersao")]),
    ])


def aba_dados():
    colunas = [
        ("ano", "Ano"), ("nome_regiao", "Região"), ("sigla_uf", "UF"),
        ("grupo_financeiro", "Grupo"), ("nome_componente", "Rubrica"),
        ("nome_esfera", "Esfera"), ("nome_porte", "Porte"), ("nome_faixa", "Faixa de valor"),
        ("valor_informado_rs", "Valor informado (R$)"),
        ("valor_informado_rs_milhares", "Valor (R$ mil)"),
        ("valor_absoluto_rs", "Valor absoluto (R$)"),
        ("quantidade_registros", "Qtd. registros"),
        ("quantidade_valores_positivos", "Qtd. positivos"),
    ]
    num = Format(precision=2, scheme=Scheme.fixed, group=Group.yes, symbol=Symbol.yes)
    inteiro = Format(precision=0, scheme=Scheme.fixed, group=Group.yes)
    cols = []
    for cid, nome in colunas:
        c = {"name": nome, "id": cid}
        if cid in ("valor_informado_rs", "valor_absoluto_rs", "valor_informado_rs_milhares"):
            c.update(type="numeric", format=num)
        elif cid.startswith("quantidade"):
            c.update(type="numeric", format=inteiro)
        cols.append(c)
    return html.Div(className="card", children=[
        html.Div(className="card-cab-flex", children=[
            titulo_card("📋", "Visualização Detalhada do Cubo da Fato (Dados Filtrados)",
                        "Agregação da fato_financeiro_anual por Ano × UF × Rubrica × Esfera × "
                        "Porte × Faixa. Clique no cabeçalho para ordenar."),
            html.Span(id="badge-registros", className="badge badge-forte")]),
        dash_table.DataTable(
            id="tabela", columns=cols, data=[], page_current=0, page_size=15,
            page_action="custom", sort_action="custom", sort_mode="single", sort_by=[],
            locale_format={"decimal": ",", "group": ".", "symbol": ["R$ ", ""]},
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#0f172a", "color": "white", "fontWeight": "600",
                          "fontFamily": "Inter, sans-serif", "fontSize": "12px",
                          "border": "none"},
            style_cell={"fontFamily": "JetBrains Mono, Consolas, monospace", "fontSize": "12px",
                        "padding": "8px 10px", "border": "none",
                        "borderBottom": "1px solid #e2e8f0", "textAlign": "left",
                        "maxWidth": "260px", "overflow": "hidden", "textOverflow": "ellipsis"},
            style_cell_conditional=[{"if": {"column_type": "numeric"}, "textAlign": "right"}],
            style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#f8fafc"},
                                    {"if": {"filter_query": "{valor_informado_rs} < 0",
                                            "column_id": "valor_informado_rs"},
                                     "color": "#b91c1c", "fontWeight": "600"}],
        ),
    ])


def aba_modelo():
    regras = DADOS.dim_componente[["codigo_componente", "nome_componente", "grupo_financeiro",
                                   "papel_analitico", "natureza_valor", "regra_temporal",
                                   "exige_esfera"]]
    total = DADOS.total_linhas_fato
    pos = int(DADOS.cubo_uf["quantidade_valores_positivos"].sum())
    fatos = [
        ("Fonte de dados ativa", DADOS.detalhe),
        ("Carregado em", DADOS.carregado_em),
        ("Linhas da fato representadas", num_br(total, 0)),
        ("Valores estritamente positivos", f"{num_br(pos, 0)} ({pct(pos / total if total else None)})"),
        ("Municípios na dim_localidade", num_br(len(DADOS.dim_localidade), 0)),
        ("Anos em dim_tempo", f"{DADOS.ano_min}–{DADOS.ano_max} ({len(DADOS.dim_tempo)} anos)"),
        ("Rubricas em dim_componente", str(len(DADOS.dim_componente))),
    ]
    return html.Div(children=[
        html.Div(className="linha", children=[
            html.Div(className="card col-7", children=[
                titulo_card("⭐", "Esquema Estrela Única — dw_snis_financeiro",
                            "1 tabela fato central + 6 dimensões diretas (sem snowflake)"),
                html.Img(src="/assets/diagrama_estrela.png", className="diagrama",
                         alt="Diagrama EER da estrela dw_snis_financeiro")]),
            html.Div(className="card col-5", children=[
                titulo_card("🧾", "Ficha Técnica do Cubo"),
                html.Table(className="ficha", children=html.Tbody([
                    html.Tr([html.Th(k), html.Td(v)]) for k, v in fatos])),
                html.H4("Grão da fato", className="sub-h"),
                html.P("Um montante financeiro efetivamente informado de uma rubrica "
                       "(dim_componente), em um município (dim_localidade), em um ano "
                       "(dim_tempo) e na esfera aplicável (dim_esfera), classificado pelo porte "
                       "(dim_porte_municipio) e pela faixa de valor (dim_faixa_valor)."),
                html.H4("Métricas aditivas (5)", className="sub-h"),
                html.Ul([html.Li(html.Code(m)) for m in (
                    "valor_informado_rs", "valor_informado_rs_milhares", "valor_absoluto_rs",
                    "quantidade_registros", "quantidade_valores_positivos")]),
                html.H4("Regras de agregação respeitadas no painel", className="sub-h"),
                html.Ul([
                    html.Li("Indicadores usam rubricas de referência (receita_operacional, "
                            "despesa_total_servico, investimento_total, arrecadacao_total) e "
                            "nunca somam totais com parcelas."),
                    html.Li("credito_a_receber é SALDO (NAO_SOMAR_ANOS): o painel mostra apenas "
                            "o último ano do recorte."),
                    html.Li("Destino (água/esgoto/outro) e origem (próprio/oneroso/não oneroso) "
                            "do investimento são exibidos em gráficos separados."),
                ]),
            ]),
        ]),
        html.Div(className="card", children=[
            titulo_card("📚", "Catálogo da dim_componente (30 rubricas)"),
            dash_table.DataTable(
                data=regras.to_dict("records"),
                columns=[{"name": c, "id": c} for c in regras.columns],
                page_size=10, sort_action="native", filter_action="native",
                style_table={"overflowX": "auto"},
                style_header={"backgroundColor": "#0f172a", "color": "white",
                              "fontWeight": "600", "border": "none"},
                style_cell={"fontFamily": "Inter, sans-serif", "fontSize": "12px",
                            "padding": "7px", "textAlign": "left", "border": "none",
                            "borderBottom": "1px solid #e2e8f0"}),
        ]),
    ])


def serve_layout():
    return html.Div(className="app", children=[
        dcc.Store(id="store-versao", data=0),
        html.Header(className="topo", children=[
            html.Div(className="topo-esq", children=[
                html.Div("💧", className="logo"),
                html.Div([
                    html.H1("DW SNIS — Painel OLAP Financeiro do Saneamento"),
                    html.P(id="fonte-dados", className="topo-sub",
                           children=f"Fonte de dados: {DADOS.detalhe} | Modelo Estrela "
                                    f"(Star Schema) dw_snis_financeiro"),
                ]),
            ]),
            dcc.Loading(
                type="circle", color="#22d3ee", parent_className="topo-acoes-wrap",
                overlay_style={"visibility": "visible", "opacity": 0.55},
                target_components={"download-csv": "data", "download-excel": "data",
                                   "fonte-dados": "children"},
                children=html.Div(className="topo-acoes", children=[
                    html.Button("⬇ Exportar CSV", id="btn-csv", className="btn btn-claro",
                                title="Exporta o cubo filtrado (todas as dimensões) em CSV"),
                    html.Button("⬇ Exportar Excel (.xlsx)", id="btn-excel",
                                className="btn btn-verde",
                                title="Dados filtrados + resumo dos KPIs + filtros aplicados"),
                    html.Button("⟳ Recarregar DW", id="btn-recarregar", className="btn btn-azul",
                                title="Relê o Data Warehouse (MySQL) sem reiniciar o servidor"),
                    dcc.Download(id="download-csv"),
                    dcc.Download(id="download-excel"),
                ])),
        ]),
        html.Div(className="corpo", children=[
            painel_filtros(),
            html.Main(className="conteudo", children=[
                dcc.Tabs(id="abas", value="exec", className="abas", children=[
                    dcc.Tab(label="Visão Executiva", value="exec", className="aba",
                            selected_className="aba-sel", children=aba_executiva()),
                    dcc.Tab(label="Composição", value="comp", className="aba",
                            selected_className="aba-sel", children=aba_composicao()),
                    dcc.Tab(label="Investimentos", value="inv", className="aba",
                            selected_className="aba-sel", children=aba_investimentos()),
                    dcc.Tab(label="Porte & Faixa", value="seg", className="aba",
                            selected_className="aba-sel", children=aba_segmentos()),
                    dcc.Tab(label="Territorial", value="ter", className="aba",
                            selected_className="aba-sel", children=aba_territorial()),
                    dcc.Tab(label="Dados", value="dados", className="aba",
                            selected_className="aba-sel", children=aba_dados()),
                    dcc.Tab(label="Modelo Estrela", value="modelo", className="aba",
                            selected_className="aba-sel", children=aba_modelo()),
                ]),
                html.Footer(className="rodape", children=[
                    "UFRPE · DEINFO · Modelagem de Dados · 2ª VA · Grupo 2 — Fonte: SNIS "
                    "(Sistema Nacional de Informações sobre Saneamento), série 1995–2022. "
                    "Valores em reais nominais."]),
            ]),
        ]),
    ])


# =====================================================================================
# 4. APLICAÇÃO DASH
# =====================================================================================
app = Dash(__name__, title="DW SNIS • Painel OLAP Financeiro",
           external_stylesheets=["https://fonts.googleapis.com/css2?family=Inter:wght@400;500;"
                                 "600;700;800&family=JetBrains+Mono:wght@400;600&display=swap"],
           external_scripts=["https://cdn.plot.ly/plotly-locale-pt-br-latest.js"],
           suppress_callback_exceptions=True)
server = app.server  # usado pelo gunicorn no Render
app.layout = serve_layout

FILTROS = [Input("f-anos", "value"), Input("f-decada", "value"), Input("f-plansab", "value"),
           Input("f-marco", "value"), Input("f-regiao", "value"), Input("f-uf", "value"),
           Input("f-esfera", "value"), Input("f-porte", "value"), Input("f-faixa", "value"),
           Input("f-escala", "value"), Input("store-versao", "data"), Input("abas", "value")]
FILTROS_STATE = [State(i.component_id, i.component_property) for i in FILTROS[:10]]


def ler_filtros(*valores):
    return montar_filtros(*valores[:10])


def somente_aba(valores, aba):
    """Desempenho: só a aba visível é recalculada; as demais atualizam ao serem abertas."""
    if valores[11] != aba:
        raise PreventUpdate


# ---------------------------------------------------------------- Callback em cascata
@app.callback(
    Output("f-uf", "options"), Output("f-uf", "value"),
    Input("f-regiao", "value"), Input("btn-uf-todos", "n_clicks"),
    Input("btn-uf-limpar", "n_clicks"), Input("btn-reset", "n_clicks"),
    Input("store-versao", "data"), State("f-uf", "value"))
def cascata_regiao_uf(regioes, _t, _l, _r, _v, ufs_atuais):
    """Região ➔ UF: ao mudar regiões, os checkboxes de UF são recriados todos marcados."""
    regioes = regioes or DADOS.regioes
    if ctx.triggered_id == "btn-reset":
        regioes = DADOS.regioes
    ufs = sorted(u for r in regioes for u in DADOS.uf_por_regiao.get(r, []))
    opcoes = [{"label": f" {u}", "value": u} for u in ufs]
    if ctx.triggered_id == "btn-uf-limpar":
        return opcoes, []
    return opcoes, ufs


@app.callback(Output("badge-ufs", "children"), Input("f-uf", "value"))
def badge_ufs(ufs):
    n = len(ufs or [])
    return f"{n} UF{'s' if n != 1 else ''} ativa{'s' if n != 1 else ''}"


# ---------------------------------------------------------------- Reset dos filtros
@app.callback(
    Output("f-anos", "value"), Output("f-decada", "value"), Output("f-plansab", "value"),
    Output("f-marco", "value"), Output("f-regiao", "value"), Output("f-esfera", "value"),
    Output("f-porte", "value"), Output("f-faixa", "value"), Output("f-escala", "value"),
    Input("btn-reset", "n_clicks"), prevent_initial_call=True)
def redefinir(_n):
    p = filtros_padrao()
    return (p["anos"], [], "TODOS", "TODOS", p["regioes"], p["esferas"], p["portes"],
            p["faixas"], p["escala"])


# ---------------------------------------------------------------- Recarregar DW
@app.callback(Output("store-versao", "data"), Output("fonte-dados", "children"),
              Input("btn-recarregar", "n_clicks"), State("store-versao", "data"),
              prevent_initial_call=True)
def recarregar(_n, versao):
    global DADOS
    DADOS = carregar_dados()
    return (versao or 0) + 1, (f"Fonte de dados: {DADOS.detalhe} | Recarregado em "
                               f"{DADOS.carregado_em} | Modelo Estrela dw_snis_financeiro")


# ---------------------------------------------------------------- Aba 1: Visão Executiva
def kpi(titulo, valor, sub, cor, dica=None):
    return html.Div(className=f"kpi {cor}", title=dica, children=[
        html.Span(titulo, className="kpi-tit"), html.Strong(valor, className="kpi-val"),
        html.Span(sub, className="kpi-sub")])


@app.callback(Output("kpis", "children"), Output("fig-evolucao", "figure"),
              Output("cards-regiao", "children"), Output("fig-uf", "figure"),
              *FILTROS, Input("sel-metrica-uf", "value"))
def atualizar_executiva(*args):
    somente_aba(args, "exec")
    f = ler_filtros(*args)
    metrica_uf = args[-1]
    df = aplicar_filtros(DADOS.cubo_uf, f)

    rec, desp = soma(df, C_RECEITA), soma(df, C_DESPESA)
    inv, arr = soma(df, C_INVEST), soma(df, C_ARRECAD)
    cred, ano_cred = saldo_ultimo_ano(df, C_CREDITO)
    res = rec - desp
    margem = razao(res, rec)
    regs = int(df["quantidade_registros"].sum())
    pos = int(df["quantidade_valores_positivos"].sum())
    n_anos = f["anos"][1] - f["anos"][0] + 1

    rec_direta = soma(df, "receita_operacional_direta")
    in012 = razao(rec_direta, desp)      # SNIS IN012 — Indicador de desempenho financeiro
    in029 = razao(rec - arr, rec)        # SNIS IN029 — Índice de evasão de receitas
    kpis = [
        kpi("Receita Operacional Total", brl_curto(rec), variacao_anual(df, C_RECEITA), "k-azul",
            f"{brl(rec)}\nSUM(valor_informado_rs) WHERE componente = receita_operacional"),
        kpi("Despesa Total dos Serviços", brl_curto(desp), variacao_anual(df, C_DESPESA),
            "k-laranja",
            f"{brl(desp)}\nSUM(valor_informado_rs) WHERE componente = despesa_total_servico"),
        kpi("Resultado Operacional", brl_curto(res), "Receita − Despesa total",
            "k-verde" if res >= 0 else "k-vermelho", brl(res)),
        kpi("Margem Operacional", pct(margem),
            f"IN012 (desempenho financeiro): {pct(in012)}", "k-ciano",
            "Margem = (receita − despesa) ÷ receita\nIN012/SNIS = receita operacional direta ÷ "
            "despesa total dos serviços"),
        kpi("Investimento Total", brl_curto(inv), variacao_anual(df, C_INVEST), "k-roxo",
            f"{brl(inv)}\nSoma das esferas selecionadas · {n_anos} ano(s)"),
        kpi("Evasão de Receitas (IN029)", pct(in029),
            f"Arrecadado: {brl_curto(arr)}", "k-amarelo",
            "IN029/SNIS = (receita operacional − arrecadação total) ÷ receita operacional"),
        kpi("Créditos a Receber (saldo)", brl_curto(cred),
            f"Saldo em {ano_cred}" if ano_cred else "Sem saldo no recorte", "k-cinza",
            "Métrica semi-aditiva: somente o último ano do recorte"),
        kpi("Declarações Informadas", num_br(regs, 0),
            f"{pct(razao(pos, regs))} com valor positivo", "k-grafite",
            "SUM(quantidade_registros) e SUM(quantidade_valores_positivos)"),
    ]

    # --- Evolução temporal
    esc, rot = div_escala(f), rotulo_escala(f)
    base = df[df["componente"].isin([C_RECEITA, C_DESPESA, C_INVEST])]
    if base.empty:
        fig_ev = figura_vazia()
    else:
        serie = (base.groupby(["ano", "componente"], observed=True)["valor_informado_rs"].sum()
                 .unstack(fill_value=0).reindex(columns=[C_RECEITA, C_DESPESA, C_INVEST],
                                                fill_value=0) / esc)
        fig_ev = go.Figure()
        fig_ev.add_bar(x=serie.index, y=serie[C_RECEITA], name="Receita operacional",
                       marker_color="#2563eb",
                       hovertemplate="%{x}<br>Receita: %{y:,.2f} " + rot + "<extra></extra>")
        fig_ev.add_bar(x=serie.index, y=serie[C_DESPESA], name="Despesa total",
                       marker_color="#f97316",
                       hovertemplate="%{x}<br>Despesa: %{y:,.2f} " + rot + "<extra></extra>")
        fig_ev.add_scatter(x=serie.index, y=serie[C_RECEITA] - serie[C_DESPESA],
                           name="Resultado", mode="lines+markers",
                           line=dict(color="#059669", width=3),
                           hovertemplate="%{x}<br>Resultado: %{y:,.2f} " + rot + "<extra></extra>")
        fig_ev.add_scatter(x=serie.index, y=serie[C_INVEST], name="Investimento total",
                           mode="lines+markers", line=dict(color="#7c3aed", width=2, dash="dot"),
                           hovertemplate="%{x}<br>Investimento: %{y:,.2f} " + rot + "<extra></extra>")
        anos = list(serie.index)
        if anos and min(anos) <= 2014 <= max(anos):
            fig_ev.add_vline(x=2013.5, line_dash="dash", line_color="#94a3b8",
                             annotation_text="PLANSAB", annotation_position="top left")
        if anos and min(anos) <= 2020 <= max(anos):
            fig_ev.add_vline(x=2019.5, line_dash="dash", line_color="#0d9488",
                             annotation_text="Marco Legal", annotation_position="top left")
        fig_ev.update_layout(barmode="group", bargap=0.18, yaxis_title=f"{rot} (valores nominais)")
        estilo(fig_ev, 440)
        eixo_anos(fig_ev, len(anos))
        fig_ev.update_xaxes(range=[min(anos) - 0.6, max(anos) + 0.6])

    # --- Cards por região
    reg = df[df["componente"].isin([C_RECEITA, C_DESPESA, C_INVEST])]
    cards = []
    if reg.empty:
        cards = [html.P("Nenhuma região no recorte.", className="vazio")]
    else:
        tab = (reg.groupby(["nome_regiao", "componente"], observed=True)["valor_informado_rs"]
               .sum().unstack(fill_value=0))
        for r in [x for x in DADOS.regioes if x in tab.index]:
            rr = tab.loc[r]
            rv, dv, iv = rr.get(C_RECEITA, 0), rr.get(C_DESPESA, 0), rr.get(C_INVEST, 0)
            mg = razao(rv - dv, rv)
            cards.append(html.Div(className="regiao-card",
                                  style={"borderLeftColor": CORES_REGIAO[r]}, children=[
                html.Div(className="regiao-top", children=[
                    html.Strong(r),
                    html.Span(f"Margem: {pct(mg)}",
                              className="pill " + ("pill-ok" if (mg or 0) >= 0 else "pill-neg"))]),
                html.Div(brl_curto(rv), className="regiao-val"),
                html.Small(f"Despesa: {brl_curto(dv)} · Invest.: {brl_curto(iv)}")]))

    # --- Barras por UF agrupadas por região
    d_uf = df[df["componente"] == metrica_uf]
    d_uf, _ = respeitar_regra_temporal(d_uf, metrica_uf)
    if d_uf.empty:
        fig_uf = figura_vazia()
    else:
        g = (d_uf.groupby(["nome_regiao", "sigla_uf", "nome_uf"], observed=True)
             ["valor_informado_rs"].sum().reset_index())
        g = txt(g)
        g["valor"] = g["valor_informado_rs"] / esc
        g["ord_reg"] = g["nome_regiao"].astype(str).map({r: i for i, r in enumerate(DADOS.regioes)})
        g = g.sort_values(["ord_reg", "valor"], ascending=[True, False])
        fig_uf = px.bar(g, x="sigla_uf", y="valor", color="nome_regiao",
                        color_discrete_map=CORES_REGIAO,
                        category_orders={"sigla_uf": list(g["sigla_uf"]),
                                         "nome_regiao": DADOS.regioes},
                        custom_data=["nome_uf", "valor_informado_rs"],
                        labels={"sigla_uf": "UF", "valor": rot, "nome_regiao": "Região"})
        fig_uf.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>%{y:,.2f} " + rot +
                                           "<extra></extra>")
        estilo(fig_uf, 400)
    return kpis, fig_ev, cards, fig_uf


# ---------------------------------------------------------------- Aba 2: Composição
@app.callback(Output("fig-composicao", "figure"), Output("fig-treemap", "figure"),
              Output("fig-heatmap", "figure"), Output("nota-rubrica", "children"),
              *FILTROS, Input("sel-grupo", "value"), Input("sel-rubrica", "value"))
def atualizar_composicao(*args):
    somente_aba(args, "comp")
    f = ler_filtros(*args)
    grupo, rubrica = args[-2], args[-1]
    df = aplicar_filtros(DADOS.cubo_uf, f)
    esc, rot = div_escala(f), rotulo_escala(f)

    # Composição: parcelas declaradas do grupo
    comp = df[(df["grupo_financeiro"] == grupo) & (df["papel_analitico"] == "RUBRICA_DECLARADA")]
    if comp.empty:
        fig_c = figura_vazia()
    else:
        g = txt(comp.groupby(["componente", "nome_componente"], observed=True)
                ["valor_informado_rs"].sum().reset_index())
        ref = REFERENCIA_GRUPO[grupo]
        total_ref = soma(df, ref)
        nome_ref = DADOS.nome_componente.get(ref, ref)
        g["classe"] = g["componente"].map(CLASSE_RUBRICA).fillna("Outras")
        g["valor"] = g["valor_informado_rs"] / esc
        g["part"] = g["valor_informado_rs"] / total_ref * 100 if total_ref else float("nan")
        ordem_classes = [c for c in CORES_CLASSE if c in set(g["classe"])]
        g["ord"] = g["classe"].map({c: i for i, c in enumerate(ordem_classes)})
        g = g.sort_values(["ord", "valor"], ascending=[False, True])
        fig_c = px.bar(g, x="valor", y="nome_componente", orientation="h", color="classe",
                       color_discrete_map=CORES_CLASSE, custom_data=["part"],
                       category_orders={"nome_componente": list(g["nome_componente"]),
                                        "classe": ordem_classes},
                       labels={"valor": rot, "nome_componente": "", "classe": "Classificação"})
        fig_c.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.2f} " + rot +
                                          f"<br>%{{customdata[0]:.1f}}% de {nome_ref}"
                                          "<extra></extra>",
                            texttemplate="%{customdata[0]:.1f}%", textposition="outside",
                            cliponaxis=False)
        fig_c.add_annotation(
            text=f"% = participação em <b>{nome_ref}</b> ({brl_curto(total_ref)}) — "
                 "não somar classificações diferentes", xref="paper", yref="paper",
            x=1, y=0, yshift=-58, xanchor="right", yanchor="top", showarrow=False,
            font=dict(size=11, color="#64748b"))
        estilo(fig_c, max(400, 34 * len(g) + 140))
        fig_c.update_layout(margin=dict(l=10, r=40, t=30, b=80))

    # Drill-down da rubrica escolhida
    d = df[df["componente"] == rubrica]
    linha = DADOS.dim_componente.set_index("codigo_componente").loc[rubrica]
    d_t, saldo = respeitar_regra_temporal(d, rubrica)
    nota = [html.Strong(linha["nome_componente"]), " · grupo ", html.Code(linha["grupo_financeiro"]),
            " · papel ", html.Code(linha["papel_analitico"]), " · natureza ",
            html.Code(linha["natureza_valor"]), " · regra temporal ",
            html.Code(linha["regra_temporal"]), html.Br(),
            html.Small(f"Regra de agregação: {linha['regra_agregacao']}")]
    if saldo and not d_t.empty:
        nota += [html.Br(), html.Small(
            f"⚠ Rubrica de SALDO: o treemap mostra apenas {int(d_t['ano'].max())} "
            "(último ano do recorte), pois saldos não podem ser somados entre anos.",
            className="alerta")]

    if d_t.empty:
        fig_t = figura_vazia()
    else:
        g = (d_t.groupby(["nome_regiao", "sigla_uf"], observed=True)["valor_informado_rs"].sum()
             .reset_index())
        g = txt(g)
        g["valor"] = (g["valor_informado_rs"] / esc).clip(lower=0)
        g = g[g["valor"] > 0]
        if g.empty:
            fig_t = figura_vazia("Sem valores positivos para o treemap")
        else:
            fig_t = px.treemap(g, path=[px.Constant("Brasil"), "nome_regiao", "sigla_uf"],
                               values="valor", color="nome_regiao",
                               color_discrete_map={**CORES_REGIAO, "(?)": "#cbd5e1"})
            fig_t.update_traces(hovertemplate="<b>%{label}</b><br>%{value:,.2f} " + rot +
                                              "<br>%{percentRoot:.1%} do total<extra></extra>",
                                texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}")
            estilo(fig_t, 420)

    if d.empty:
        fig_h = figura_vazia()
    else:
        h = (d.groupby(["nome_regiao", "ano"], observed=True)["valor_informado_rs"].sum()
             .unstack(fill_value=0) / esc)
        h = h.reindex([r for r in DADOS.regioes if r in h.index])
        tot_ano = h.sum(axis=0).replace(0, float("nan"))
        part = (h / tot_ano * 100).fillna(0)
        fig_h = go.Figure(go.Heatmap(
            z=part.to_numpy(dtype=float), x=[int(a) for a in h.columns],
            y=[str(r) for r in h.index], customdata=h.to_numpy(dtype=float),
            colorscale="Blues", zmin=0, colorbar=dict(title="% do ano", ticksuffix="%"),
            hovertemplate="%{y} · %{x}<br>%{z:.1f}% do total do ano<br>%{customdata:,.2f} "
                          + rot + "<extra></extra>"))
        estilo(fig_h, 420, legenda_h=False)
        eixo_anos(fig_h, len(h.columns))
    return fig_c, fig_t, fig_h, nota


# ---------------------------------------------------------------- Aba 3: Investimentos
@app.callback(Output("fig-inv-esfera", "figure"), Output("fig-inv-origem", "figure"),
              Output("fig-inv-destino", "figure"), Output("fig-inv-marco", "figure"), *FILTROS)
def atualizar_investimentos(*args):
    somente_aba(args, "inv")
    f = ler_filtros(*args)
    df = aplicar_filtros(DADOS.cubo_uf, f)
    esc, rot = div_escala(f), rotulo_escala(f)
    inv = df[df["grupo_financeiro"] == "INVESTIMENTOS"].copy()
    if inv.empty:
        vazio = figura_vazia("Sem investimentos (verifique a dimensão Esfera)")
        return vazio, vazio, vazio, vazio
    inv["nome_esfera"] = inv["esfera"].astype(str).map(DADOS.nome_esfera)

    t = inv[inv["componente"] == C_INVEST]
    if t.empty:
        fig_e = figura_vazia()
    else:
        g = t.groupby(["ano", "nome_esfera"], observed=True)["valor_informado_rs"].sum().reset_index()
        g = txt(g)
        g["valor"] = g["valor_informado_rs"] / esc
        fig_e = px.bar(g, x="ano", y="valor", color="nome_esfera",
                       color_discrete_map=CORES_ESFERA, category_orders={"nome_esfera": ESFERAS_NOMES},
                       labels={"ano": "Ano", "valor": rot, "nome_esfera": "Esfera"})
        fig_e.update_traces(hovertemplate="%{x}<br>%{y:,.2f} " + rot + "<extra>%{fullData.name}</extra>")
        fig_e.update_layout(barmode="stack")
        estilo(fig_e, 400)
        eixo_anos(fig_e, g["ano"].nunique())

    o = inv[inv["componente"].isin(ORIGENS_INV)]
    if o.empty:
        fig_o = figura_vazia()
    else:
        g = txt(o.groupby("componente", observed=True)["valor_informado_rs"].sum().reset_index())
        g["origem"] = g["componente"].map(NOMES_CURTOS_INV)
        g["valor_informado_rs"] = g["valor_informado_rs"].clip(lower=0)
        fig_o = px.pie(g, names="origem", values="valor_informado_rs", hole=0.55,
                       color="origem",
                       color_discrete_map={"Recursos próprios": "#0d9488",
                                           "Recursos onerosos": "#f59e0b",
                                           "Recursos não onerosos": "#6366f1"},
                       category_orders={"origem": ["Recursos próprios", "Recursos onerosos",
                                                   "Recursos não onerosos"]})
        fig_o.update_traces(hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}"
                                          "<extra></extra>", textinfo="percent")
        total = g["valor_informado_rs"].sum()
        fig_o.add_annotation(text=f"<b>{brl_curto(total)}</b><br>total", showarrow=False,
                             font=dict(size=13))
        estilo(fig_o, 400)
        fig_o.update_traces(sort=False)

    dd = inv[inv["componente"].isin(DESTINOS_INV)]
    if dd.empty:
        fig_d = figura_vazia()
    else:
        g = txt(dd.groupby(["componente", "nome_esfera"], observed=True)["valor_informado_rs"]
                .sum().reset_index())
        g["destino"] = g["componente"].map(NOMES_CURTOS_INV)
        g["valor"] = g["valor_informado_rs"] / esc
        fig_d = px.bar(g, x="destino", y="valor", color="nome_esfera", barmode="group",
                       color_discrete_map=CORES_ESFERA,
                       category_orders={"nome_esfera": ESFERAS_NOMES,
                                        "destino": ["Água", "Esgoto", "Outros"]},
                       labels={"destino": "Destino do investimento", "valor": rot,
                               "nome_esfera": "Esfera"})
        fig_d.update_traces(hovertemplate="%{x}<br>%{y:,.2f} " + rot + "<extra>%{fullData.name}</extra>")
        estilo(fig_d, 380)

    if t.empty:
        fig_m = figura_vazia()
    else:
        # Comparação justa: mesma duração antes e depois da Lei 14.026/2020
        # (os 3 anos pós-lei contra os 3 anos imediatamente anteriores do recorte)
        anos_pos = sorted(a for a in t["ano"].unique() if a >= 2020)
        anos_pre = sorted(a for a in t["ano"].unique() if a < 2020)
        if anos_pos:
            anos_pre = [a for a in anos_pre if a >= 2020 - len(anos_pos)]
        janela = t[t["ano"].isin(anos_pre + anos_pos)].copy()
        rot_pre = f"Pré-Marco ({min(anos_pre)}–{max(anos_pre)})" if anos_pre else "Pré-Marco"
        rot_pos = f"Pós-Marco ({min(anos_pos)}–{max(anos_pos)})" if anos_pos else "Pós-Marco"
        janela["periodo"] = janela["ano"].map(lambda a: rot_pos if a >= 2020 else rot_pre)
        n_anos = {rot_pre: max(len(anos_pre), 1), rot_pos: max(len(anos_pos), 1)}
        g = (janela.groupby(["nome_regiao", "periodo"], observed=True)["valor_informado_rs"]
             .sum().reset_index())
        g = txt(g)
        g["media_anual"] = g["valor_informado_rs"] / g["periodo"].map(n_anos) / esc
        fig_m = px.bar(g, x="nome_regiao", y="media_anual", color="periodo", barmode="group",
                       color_discrete_map={rot_pre: "#94a3b8", rot_pos: "#0d9488"},
                       category_orders={"nome_regiao": DADOS.regioes,
                                        "periodo": [rot_pre, rot_pos]},
                       labels={"nome_regiao": "Região", "media_anual": f"{rot} por ano",
                               "periodo": "Período"})
        fig_m.update_traces(hovertemplate="%{x}<br>Média anual: %{y:,.2f} " + rot +
                                          "<extra>%{fullData.name}</extra>")
        estilo(fig_m, 380)
    return fig_e, fig_o, fig_d, fig_m


# ---------------------------------------------------------------- Aba 4: Porte e Faixa
@app.callback(Output("fig-porte", "figure"), Output("fig-faixa", "figure"),
              Output("fig-porte-faixa", "figure"), Output("fig-positivos", "figure"), *FILTROS)
def atualizar_segmentos(*args):
    somente_aba(args, "seg")
    f = ler_filtros(*args)
    df = aplicar_filtros(DADOS.cubo_uf, f)
    esc, rot = div_escala(f), rotulo_escala(f)
    if df.empty:
        v = figura_vazia()
        return v, v, v, v
    ordem_porte = [DADOS.nome_porte[c] for c in DADOS.dim_porte.codigo_porte]
    ordem_faixa = [FAIXA_CURTA.get(c, DADOS.nome_faixa[c]) for c in DADOS.dim_faixa.codigo_faixa]

    p = df[df["componente"].isin([C_RECEITA, C_DESPESA, C_INVEST])].copy()
    if p.empty:
        fig_p = figura_vazia()
    else:
        p["nome_porte"] = p["porte"].astype(str).map(DADOS.nome_porte)
        p["rubrica"] = p["componente"].astype(str).map(DADOS.nome_componente)
        g = p.groupby(["nome_porte", "rubrica"], observed=True)["valor_informado_rs"].sum().reset_index()
        g = txt(g)
        g["valor"] = g["valor_informado_rs"] / esc
        fig_p = px.bar(g, x="nome_porte", y="valor", color="rubrica", barmode="group",
                       category_orders={"nome_porte": ordem_porte, "rubrica": list(CORES_RUBRICA)},
                       color_discrete_map=CORES_RUBRICA,
                       labels={"nome_porte": "", "valor": rot, "rubrica": "Rubrica"})
        fig_p.update_traces(hovertemplate="%{x}<br>%{y:,.2f} " + rot + "<extra>%{fullData.name}</extra>")
        estilo(fig_p, 400)

    d = df.copy()
    d["nome_faixa"] = d["faixa"].astype(str).map(lambda c: FAIXA_CURTA.get(c, DADOS.nome_faixa[c]))
    d["nome_porte"] = d["porte"].astype(str).map(DADOS.nome_porte)
    g = d.groupby("nome_faixa", observed=True)[["quantidade_registros"]].sum().reset_index()
    g = txt(g)
    g["pct"] = g["quantidade_registros"] / g["quantidade_registros"].sum() * 100
    fig_f = px.bar(g, x="nome_faixa", y="quantidade_registros", color="nome_faixa",
                   category_orders={"nome_faixa": ordem_faixa}, custom_data=["pct"],
                   color_discrete_sequence=["#dc2626", "#94a3b8", "#99f6e4", "#2dd4bf",
                                            "#0d9488", "#115e59"],
                   labels={"nome_faixa": "", "quantidade_registros": "Declarações"})
    fig_f.update_traces(texttemplate="%{customdata[0]:.1f}%", textposition="outside",
                        cliponaxis=False,
                        hovertemplate="%{x}<br>%{y:,.0f} declarações (%{customdata[0]:.2f}%)"
                                      "<extra></extra>")
    fig_f.update_layout(showlegend=False, xaxis_title="Faixa do valor declarado (R$)")
    estilo(fig_f, 400)

    h = (d.groupby(["nome_porte", "nome_faixa"], observed=True)["quantidade_registros"].sum()
         .unstack(fill_value=0)
         .reindex(index=[x for x in ordem_porte if x in set(d["nome_porte"])],
                  columns=[x for x in ordem_faixa if x in set(d["nome_faixa"])], fill_value=0))
    fig_h = go.Figure(go.Heatmap(z=h.to_numpy(dtype=float), x=[str(c) for c in h.columns],
                                 y=[str(r) for r in h.index], colorscale="Teal",
                                 text=h.to_numpy(dtype=float), texttemplate="%{text:,.0f}",
                                 hovertemplate="%{y} · %{x}<br>%{z:,.0f} declarações"
                                               "<extra></extra>"))
    estilo(fig_h, 400, legenda_h=False)
    fig_h.update_yaxes(autorange="reversed")
    fig_h.update_xaxes(title_text="Faixa do valor declarado (R$)")

    q = df.groupby("ano", observed=True)[["quantidade_registros",
                                         "quantidade_valores_positivos"]].sum()
    q["pct"] = q["quantidade_valores_positivos"] / q["quantidade_registros"] * 100
    fig_q = make_subplots(specs=[[{"secondary_y": True}]])
    fig_q.add_bar(x=q.index, y=q["quantidade_registros"], name="Declarações informadas",
                  marker_color="#cbd5e1", hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>",
                  secondary_y=False)
    fig_q.add_scatter(x=q.index, y=q["pct"], name="% com valor positivo", mode="lines+markers",
                      line=dict(color="#0d9488", width=3),
                      hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>", secondary_y=True)
    fig_q.update_yaxes(title_text="Declarações", secondary_y=False)
    fig_q.update_yaxes(title_text="% positivos", range=[0, 100], secondary_y=True)
    estilo(fig_q, 400)
    eixo_anos(fig_q, len(q))
    return fig_p, fig_f, fig_h, fig_q


# ---------------------------------------------------------------- Aba 5: Territorial
@app.callback(Output("fig-mapa", "figure"), Output("fig-ranking", "figure"),
              Output("fig-dispersao", "figure"),
              *FILTROS, Input("sel-rubrica-mun", "value"), Input("sel-topn", "value"),
              Input("sel-margem", "value"))
def atualizar_territorial(*args):
    somente_aba(args, "ter")
    f = ler_filtros(*args)
    rubrica, topn = args[-3], int(args[-2] or 15)
    faixa_margem = args[-1] or [-100, 100]
    dm = aplicar_filtros(DADOS.cubo_mun, f)
    esc, rot = div_escala(f), rotulo_escala(f)
    loc = DADOS.localidades

    d = dm[dm["componente"] == rubrica]
    d, saldo = respeitar_regra_temporal(d, rubrica)
    if d.empty:
        fig_mapa = fig_rank = figura_vazia()
    else:
        g = d.groupby("codigo_ibge", observed=True)["valor_informado_rs"].sum()
        g = g[g != 0].to_frame("valor_rs")
        g.index = g.index.astype(str)
        g = g.join(loc[["nome_municipio", "sigla_uf", "nome_regiao", "latitude", "longitude"]])
        g["valor"] = g["valor_rs"] / esc
        g["tamanho"] = g["valor_rs"].abs()
        sufixo = f" (saldo {int(d['ano'].max())})" if saldo else ""
        top_mapa = g.dropna(subset=["latitude"]).nlargest(2500, "tamanho")
        if top_mapa.empty:
            fig_mapa = figura_vazia()
        else:
            # Mapa vetorial (MapLibre) com enquadramento automático no recorte filtrado
            lat0, lat1 = top_mapa["latitude"].min(), top_mapa["latitude"].max()
            lon0, lon1 = top_mapa["longitude"].min(), top_mapa["longitude"].max()
            extensao = max(lat1 - lat0, (lon1 - lon0) * 0.75, 0.5)
            zoom = float(max(2.6, min(8.0, math.log2(360 / extensao) - 1.6)))
            mapa = getattr(px, "scatter_map", None) or px.scatter_mapbox
            fig_mapa = mapa(
                top_mapa, lat="latitude", lon="longitude", size="tamanho", color="nome_regiao",
                color_discrete_map=CORES_REGIAO, size_max=30, hover_name="nome_municipio",
                custom_data=["sigla_uf", "valor"], category_orders={"nome_regiao": DADOS.regioes},
                labels={"nome_regiao": "Região"}, opacity=0.75, zoom=zoom,
                center={"lat": (lat0 + lat1) / 2, "lon": (lon0 + lon1) / 2})
            fig_mapa.update_traces(hovertemplate="<b>%{hovertext}</b> (%{customdata[0]})<br>"
                                                 "%{customdata[1]:,.2f} " + rot + sufixo +
                                                 "<extra></extra>")
            estilo(fig_mapa, 560)
            if getattr(px, "scatter_map", None) is None:  # plotly < 5.24
                fig_mapa.update_layout(mapbox_style="carto-positron")
            else:
                fig_mapa.update_layout(map_style="carto-positron")
            fig_mapa.update_layout(margin=dict(l=0, r=0, t=30, b=0))

        top = g.nlargest(topn, "valor").sort_values("valor")
        top["rotulo"] = top["nome_municipio"] + " (" + top["sigla_uf"].astype(str) + ")"
        fig_rank = px.bar(top, x="valor", y="rotulo", orientation="h", color="nome_regiao",
                          color_discrete_map=CORES_REGIAO,
                          labels={"valor": rot + sufixo, "rotulo": "", "nome_regiao": "Região"})
        fig_rank.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.2f} " + rot + "<extra></extra>")
        fig_rank.update_layout(yaxis={"categoryorder": "total ascending"})
        estilo(fig_rank, max(420, 26 * len(top) + 120))

    s = dm[dm["componente"].isin([C_RECEITA, C_DESPESA, C_INVEST])]
    if s.empty:
        fig_s = figura_vazia()
    else:
        p = (s.groupby(["codigo_ibge", "componente"], observed=True)["valor_informado_rs"].sum()
             .unstack(fill_value=0).reindex(columns=[C_RECEITA, C_DESPESA, C_INVEST], fill_value=0))
        p = p[(p[C_RECEITA] > 0) & (p[C_DESPESA] > 0)].copy()
        p.index = p.index.astype(str)
        p["margem"] = ((p[C_RECEITA] - p[C_DESPESA]) / p[C_RECEITA] * 100).clip(-100, 100)
        p = p[p["margem"].between(faixa_margem[0], faixa_margem[1])].copy()
        if p.empty:
            fig_s = figura_vazia("Nenhum município com receita e despesa na faixa de margem "
                                 "selecionada")
        else:
            p["inv"] = p[C_INVEST].clip(lower=0) + 1
            p = p.nlargest(600, C_RECEITA).join(loc[["nome_municipio", "sigla_uf", "nome_regiao"]])
            p["receita"] = p[C_RECEITA] / esc
            p["despesa"] = p[C_DESPESA] / esc
            p["investimento"] = p[C_INVEST] / esc
            fig_s = px.scatter(p, x="receita", y="margem", size="inv", color="nome_regiao",
                               color_discrete_map=CORES_REGIAO, size_max=40, log_x=True,
                               hover_name="nome_municipio", opacity=0.72,
                               category_orders={"nome_regiao": DADOS.regioes},
                               custom_data=["sigla_uf", "despesa", "investimento"],
                               labels={"receita": f"Receita operacional ({rot}, escala log)",
                                       "margem": "Margem operacional (%)",
                                       "nome_regiao": "Região"})
            fig_s.update_traces(hovertemplate="<b>%{hovertext}</b> (%{customdata[0]})<br>"
                                              "Receita: %{x:,.2f} " + rot + "<br>Despesa: "
                                              "%{customdata[1]:,.2f} " + rot + "<br>Margem: "
                                              "%{y:.1f}%<br>Investimento: %{customdata[2]:,.2f} "
                                              + rot + "<extra></extra>",
                                marker_line=dict(width=0.5, color="white"))
            fig_s.add_hline(y=0, line_dash="dot", line_color="#64748b")
            estilo(fig_s, 520)
            fig_s.update_xaxes(dtick=1)
    return fig_mapa, fig_rank, fig_s


# ---------------------------------------------------------------- Aba 6: Tabela
def dados_detalhados(f):
    df = aplicar_filtros(DADOS.cubo_uf, f)
    out = df[["ano", "nome_regiao", "sigla_uf", "nome_uf", "grupo_financeiro", "componente",
              "nome_componente", "esfera", "porte", "faixa", "valor_informado_rs",
              "valor_informado_rs_milhares", "valor_absoluto_rs", "quantidade_registros",
              "quantidade_valores_positivos"]].copy()
    for c in out.select_dtypes("category").columns:
        out[c] = out[c].astype(str)
    out.insert(8, "nome_esfera", out["esfera"].map(DADOS.nome_esfera))
    out.insert(10, "nome_porte", out["porte"].map(DADOS.nome_porte))
    out.insert(12, "nome_faixa", out["faixa"].map(DADOS.nome_faixa))
    return out.sort_values(["ano", "sigla_uf", "componente"]).reset_index(drop=True)


@app.callback(Output("tabela", "data"), Output("tabela", "page_count"),
              Output("badge-registros", "children"), Output("tabela", "page_current"),
              *FILTROS, Input("tabela", "page_current"), Input("tabela", "page_size"),
              Input("tabela", "sort_by"))
def atualizar_tabela(*args):
    somente_aba(args, "dados")
    f = ler_filtros(*args)
    pagina, tamanho, ordem = args[-3] or 0, args[-2] or 15, args[-1] or []
    if ctx.triggered_id not in ("tabela", "abas", None):
        pagina = 0  # um filtro mudou: volta para a primeira página
    df = dados_detalhados(f)
    if ordem:
        df = df.sort_values(ordem[0]["column_id"], ascending=ordem[0]["direction"] == "asc")
    n = len(df)
    paginas = max(1, -(-n // tamanho))
    pagina = min(pagina, paginas - 1)
    fatia = df.iloc[pagina * tamanho:(pagina + 1) * tamanho]
    linhas = int(df["quantidade_registros"].sum()) if n else 0
    return (fatia.to_dict("records"), paginas,
            f"{num_br(n, 0)} linhas do cubo · {num_br(linhas, 0)} registros da fato", pagina)


# ---------------------------------------------------------------- Exportações
def descrever_filtros(f):
    return pd.DataFrame([
        ("Período (anos)", f"{f['anos'][0]}–{f['anos'][1]}"),
        ("Décadas", ", ".join(map(str, f["decadas"])) or "Todas"),
        ("PLANSAB", f["plansab"]), ("Marco Legal", f["marco"]),
        ("Regiões", ", ".join(f["regioes"]) or "Todas"), ("UFs", ", ".join(f["ufs"]) or "Nenhuma"),
        ("Esferas", ", ".join(f["esferas"])), ("Portes", ", ".join(f["portes"])),
        ("Faixas de valor", ", ".join(f["faixas"])), ("Fonte", DADOS.detalhe),
        ("Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
    ], columns=["Filtro", "Valor"])


def resumo_kpis(f):
    df = aplicar_filtros(DADOS.cubo_uf, f)
    rec, desp = soma(df, C_RECEITA), soma(df, C_DESPESA)
    cred, ano = saldo_ultimo_ano(df, C_CREDITO)
    return pd.DataFrame([
        ("Receita operacional total (R$)", rec), ("Despesa total dos serviços (R$)", desp),
        ("Resultado operacional (R$)", rec - desp),
        ("Margem operacional (%)", (razao(rec - desp, rec) or 0) * 100),
        ("Investimento total (R$)", soma(df, C_INVEST)),
        ("Arrecadação total (R$)", soma(df, C_ARRECAD)),
        ("IN012 - Desempenho financeiro (%)",
         (razao(soma(df, "receita_operacional_direta"), desp) or 0) * 100),
        ("IN029 - Evasão de receitas (%)", (razao(rec - soma(df, C_ARRECAD), rec) or 0) * 100),
        (f"Créditos a receber - saldo {ano or ''} (R$)", cred),
        ("Declarações informadas", int(df["quantidade_registros"].sum())),
        ("Declarações com valor positivo", int(df["quantidade_valores_positivos"].sum())),
    ], columns=["Indicador", "Valor"])


@app.callback(Output("download-csv", "data"), Input("btn-csv", "n_clicks"), *FILTROS_STATE,
              prevent_initial_call=True)
def exportar_csv(_n, *estado):
    f = montar_filtros(*estado)
    csv = dados_detalhados(f).to_csv(index=False, sep=";", decimal=",")
    nome = f"dw_snis_financeiro_filtrado_{datetime.now():%Y%m%d_%H%M}.csv"
    return dcc.send_string("﻿" + csv, nome)  # BOM utf-8-sig: acentos corretos no Excel


@app.callback(Output("download-excel", "data"), Input("btn-excel", "n_clicks"), *FILTROS_STATE,
              prevent_initial_call=True)
def exportar_excel(_n, *estado):
    f = montar_filtros(*estado)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        dados_detalhados(f).to_excel(xw, sheet_name="DW_SNIS_Filtrado", index=False)
        resumo_kpis(f).to_excel(xw, sheet_name="Resumo_KPIs", index=False)
        descrever_filtros(f).to_excel(xw, sheet_name="Filtros_Aplicados", index=False)
        for ws in xw.sheets.values():
            for col in ws.columns:
                largura = max(len(str(c.value or "")) for c in list(col)[:200]) + 2
                ws.column_dimensions[col[0].column_letter].width = min(largura, 45)
            ws.freeze_panes = "A2"
    nome = f"dw_snis_financeiro_filtrado_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return dcc.send_bytes(buf.getvalue(), nome)


# =====================================================================================
# 5. EXECUÇÃO
# =====================================================================================
if __name__ == "__main__":
    porta = int(os.getenv("PORT", "8050"))
    host = "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"
    url = f"http://127.0.0.1:{porta}"
    print(f"Servidor Plotly Dash Iniciado com Sucesso! Acesse: {url}")
    # ABRIR_NAVEGADOR=1 (usado pelos iniciadores) abre o painel no navegador padrão
    if os.getenv("ABRIR_NAVEGADOR") == "1" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        import webbrowser
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    # DASH_RELOAD=1 (usado pelo iniciar_dashboard.bat) reinicia o servidor sozinho
    # sempre que um arquivo .py for salvo — prático durante o desenvolvimento.
    app.run(host=host, port=porta, debug=os.getenv("DASH_DEBUG", "0") == "1",
            use_reloader=os.getenv("DASH_RELOAD", "0") == "1")
