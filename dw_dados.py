"""
Camada de acesso ao Data Warehouse  dw_snis_financeiro  (Esquema Estrela Única).

Fonte de dados (variável de ambiente DW_FONTE):
    auto      -> tenta o MySQL; se não conectar ou a fato estiver vazia, usa o snapshot (padrão)
    mysql     -> obrigatoriamente MySQL (erro se não conectar)
    snapshot  -> usa os arquivos da pasta data/ (modo nuvem / Render)

As consultas OLAP executam o ROLL-UP diretamente no MySQL (JOIN da fato com as
6 dimensões + GROUP BY), devolvendo ao Pandas um cubo agregado. O dashboard
então faz SLICE / DICE / DRILL-DOWN em memória a cada interação (callbacks).
"""
import json
import os
from datetime import datetime

import pandas as pd

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.join(PASTA, "data")

# ------------------------------------------------------------------
# CONFIGURAÇÃO DA CONEXÃO COM O DATA WAREHOUSE (MYSQL)
# Substitua a senha abaixo ou defina as variáveis de ambiente DW_MYSQL_*
# ------------------------------------------------------------------
MYSQL_USER = os.getenv("DW_MYSQL_USER", "root")
MYSQL_PASS = os.getenv("DW_MYSQL_PASS", "sua_senha_aqui")
MYSQL_HOST = os.getenv("DW_MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("DW_MYSQL_PORT", "3306")
MYSQL_DB = os.getenv("DW_MYSQL_DB", "dw_snis_financeiro")
DB_URL = (f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/"
          f"{MYSQL_DB}?charset=utf8mb4")
FONTE = os.getenv("DW_FONTE", "auto").lower()

# Rubricas exportadas no cubo municipal (ranking, mapa e dispersão)
COMPONENTES_MUNICIPAIS = (
    "receita_operacional", "despesa_total_servico", "despesa_exploracao",
    "investimento_total", "arrecadacao_total", "credito_a_receber",
)

# ------------------------------------------------------------------
# CONSULTAS OLAP (as mesmas estão documentadas em sql/02_consultas_olap_dashboard.sql)
# Para os rótulos usa-se a versão vigente de cada membro (maior version por chave
# natural); as chaves substitutas da fato preservam o histórico (SCD).
# ------------------------------------------------------------------
SQL_CUBO_UF = """
SELECT  t.ano,
        l.sigla_uf,
        c.codigo_componente AS componente,
        e.codigo_esfera     AS esfera,
        p.codigo_porte      AS porte,
        fv.codigo_faixa     AS faixa,
        SUM(f.valor_informado_rs)           AS valor_informado_rs,
        SUM(f.valor_absoluto_rs)            AS valor_absoluto_rs,
        SUM(f.quantidade_registros)         AS quantidade_registros,
        SUM(f.quantidade_valores_positivos) AS quantidade_valores_positivos
FROM fato_financeiro_anual f
JOIN dim_tempo           t  ON t.sk_tempo            = f.sk_tempo
JOIN dim_localidade      l  ON l.sk_localidade       = f.sk_localidade
JOIN dim_componente      c  ON c.sk_componente       = f.sk_componente
JOIN dim_esfera          e  ON e.sk_esfera           = f.sk_esfera
JOIN dim_porte_municipio p  ON p.sk_porte_municipio  = f.sk_porte_municipio
JOIN dim_faixa_valor     fv ON fv.sk_faixa_valor     = f.sk_faixa_valor
GROUP BY t.ano, l.sigla_uf, c.codigo_componente, e.codigo_esfera, p.codigo_porte, fv.codigo_faixa
"""

SQL_CUBO_MUNICIPIO = """
SELECT  t.ano,
        l.codigo_ibge,
        c.codigo_componente AS componente,
        e.codigo_esfera     AS esfera,
        p.codigo_porte      AS porte,
        fv.codigo_faixa     AS faixa,
        f.valor_informado_rs
FROM fato_financeiro_anual f
JOIN dim_tempo           t  ON t.sk_tempo            = f.sk_tempo
JOIN dim_localidade      l  ON l.sk_localidade       = f.sk_localidade
JOIN dim_componente      c  ON c.sk_componente       = f.sk_componente
JOIN dim_esfera          e  ON e.sk_esfera           = f.sk_esfera
JOIN dim_porte_municipio p  ON p.sk_porte_municipio  = f.sk_porte_municipio
JOIN dim_faixa_valor     fv ON fv.sk_faixa_valor     = f.sk_faixa_valor
WHERE c.codigo_componente IN ({lista})
"""

def _sql_versao_vigente(tabela, natural, colunas):
    """Versão vigente de cada membro (maior `version` por chave natural).
    Não depende do valor de date_to usado pelo Pentaho (ex.: 2199-12-31 ou 9999-12-31)."""
    return (f"SELECT {colunas} FROM {tabela} d "
            f"WHERE d.{natural} IS NOT NULL AND d.version = "
            f"(SELECT MAX(v.version) FROM {tabela} v WHERE v.{natural} = d.{natural})")


SQL_DIMENSOES = {
    "dim_localidade": _sql_versao_vigente(
        "dim_localidade", "codigo_ibge",
        "d.codigo_ibge, d.nome_municipio, d.sigla_uf, d.nome_uf, d.nome_regiao"),
    "dim_tempo": _sql_versao_vigente(
        "dim_tempo", "ano",
        "d.ano, d.rotulo_ano, d.seculo, d.decada, d.trienio_inicio, d.quinquenio_inicio, "
        "d.periodo_plansab, d.periodo_marco_legal"),
    "dim_componente": _sql_versao_vigente(
        "dim_componente", "codigo_componente",
        "d.codigo_componente, d.nome_componente, d.grupo_financeiro, d.papel_analitico, "
        "d.natureza_valor, d.regra_temporal, d.exige_esfera, d.tabela_origem, d.regra_agregacao"),
    "dim_esfera": _sql_versao_vigente(
        "dim_esfera", "codigo_esfera", "d.codigo_esfera, d.nome_esfera, d.descricao_esfera"),
    "dim_porte_municipio": _sql_versao_vigente(
        "dim_porte_municipio", "codigo_porte",
        "d.codigo_porte, d.nome_porte, d.faixa_populacional_descricao, d.ordem_porte"),
    "dim_faixa_valor": _sql_versao_vigente(
        "dim_faixa_valor", "codigo_faixa",
        "d.codigo_faixa, d.nome_faixa, d.limite_inferior_rs, d.limite_superior_rs, d.ordem_faixa"),
}


class DadosDW:
    """Contêiner com dimensões e cubos já prontos para o dashboard."""

    def __init__(self, dims, cubo_uf, cubo_mun, coords, origem, detalhe):
        self.origem = origem              # "MySQL" ou "Snapshot"
        self.detalhe = detalhe            # texto exibido no cabeçalho
        self.carregado_em = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.dim_localidade = dims["dim_localidade"]
        self.dim_tempo = dims["dim_tempo"].sort_values("ano").reset_index(drop=True)
        self.dim_componente = dims["dim_componente"]
        self.dim_esfera = dims["dim_esfera"]
        self.dim_porte = dims["dim_porte_municipio"].sort_values("ordem_porte").reset_index(drop=True)
        self.dim_faixa = dims["dim_faixa_valor"].sort_values("ordem_faixa").reset_index(drop=True)
        self._preparar(cubo_uf, cubo_mun, coords)

    # --------------------------------------------------------------
    def _preparar(self, cubo_uf, cubo_mun, coords):
        uf_info = (self.dim_localidade[["sigla_uf", "nome_uf", "nome_regiao"]]
                   .drop_duplicates("sigla_uf"))
        tempo = self.dim_tempo[["ano", "decada", "periodo_plansab", "periodo_marco_legal"]]
        comp = self.dim_componente[["codigo_componente", "nome_componente", "grupo_financeiro",
                                    "papel_analitico", "regra_temporal"]].rename(
            columns={"codigo_componente": "componente"})

        cubo_uf = cubo_uf.copy()
        for col in ("valor_informado_rs", "valor_absoluto_rs"):
            cubo_uf[col] = pd.to_numeric(cubo_uf[col], errors="coerce").fillna(0.0).astype(float)
        for col in ("quantidade_registros", "quantidade_valores_positivos"):
            cubo_uf[col] = pd.to_numeric(cubo_uf[col], errors="coerce").fillna(0).astype("int64")
        cubo_uf["ano"] = cubo_uf["ano"].astype(int)
        cubo_uf["valor_informado_rs_milhares"] = cubo_uf["valor_informado_rs"] / 1000.0
        cubo_uf = (cubo_uf.merge(uf_info, on="sigla_uf", how="left")
                          .merge(tempo, on="ano", how="left")
                          .merge(comp, on="componente", how="left"))
        for col in ("sigla_uf", "nome_uf", "nome_regiao", "componente", "esfera", "porte", "faixa",
                    "nome_componente", "grupo_financeiro", "papel_analitico", "regra_temporal",
                    "periodo_plansab", "periodo_marco_legal"):
            cubo_uf[col] = cubo_uf[col].astype("category")
        self.cubo_uf = cubo_uf

        loc = self.dim_localidade.merge(coords, on="codigo_ibge", how="left")
        cubo_mun = cubo_mun.copy()
        cubo_mun["codigo_ibge"] = cubo_mun["codigo_ibge"].astype(str)
        cubo_mun["ano"] = cubo_mun["ano"].astype(int)
        cubo_mun["valor_informado_rs"] = pd.to_numeric(cubo_mun["valor_informado_rs"],
                                                       errors="coerce").fillna(0.0).astype(float)
        cubo_mun = (cubo_mun.merge(loc[["codigo_ibge", "sigla_uf", "nome_regiao"]],
                                   on="codigo_ibge", how="left")
                            .merge(tempo, on="ano", how="left"))
        for col in ("codigo_ibge", "sigla_uf", "nome_regiao", "componente", "esfera", "porte",
                    "faixa", "periodo_plansab", "periodo_marco_legal"):
            cubo_mun[col] = cubo_mun[col].astype("category")
        self.cubo_mun = cubo_mun
        self.localidades = loc.set_index("codigo_ibge")

        # Rótulos legíveis
        self.nome_componente = dict(zip(self.dim_componente.codigo_componente,
                                        self.dim_componente.nome_componente))
        self.nome_esfera = dict(zip(self.dim_esfera.codigo_esfera, self.dim_esfera.nome_esfera))
        self.nome_porte = dict(zip(self.dim_porte.codigo_porte, self.dim_porte.nome_porte))
        self.nome_faixa = dict(zip(self.dim_faixa.codigo_faixa, self.dim_faixa.nome_faixa))
        self.regra_temporal = dict(zip(self.dim_componente.codigo_componente,
                                       self.dim_componente.regra_temporal))
        self.regioes = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
        self.uf_por_regiao = (self.dim_localidade.drop_duplicates("sigla_uf")
                              .groupby("nome_regiao")["sigla_uf"].apply(sorted).to_dict())
        self.ano_min = int(self.dim_tempo.ano.min())
        self.ano_max = int(self.dim_tempo.ano.max())

    @property
    def total_linhas_fato(self):
        return int(self.cubo_uf["quantidade_registros"].sum())


# ------------------------------------------------------------------
def _ler_coordenadas():
    caminho = os.path.join(PASTA_DADOS, "aux_coordenadas_municipios.csv")
    if os.path.exists(caminho):
        return pd.read_csv(caminho, dtype={"codigo_ibge": str})
    return pd.DataFrame(columns=["codigo_ibge", "longitude", "latitude"])


def carregar_do_mysql():
    from sqlalchemy import create_engine, text  # import tardio: snapshot não exige driver

    engine = create_engine(DB_URL, pool_pre_ping=True, connect_args={"connect_timeout": 4})
    with engine.connect() as con:
        n = con.execute(text("SELECT COUNT(*) FROM fato_financeiro_anual")).scalar()
        if not n:
            raise RuntimeError("fato_financeiro_anual está vazia (rode a carga no Pentaho)")
        dims = {nome: pd.read_sql(text(sql), con) for nome, sql in SQL_DIMENSOES.items()}
        dims["dim_localidade"]["codigo_ibge"] = dims["dim_localidade"]["codigo_ibge"].astype(str).str.strip()
        for nome, col in (("dim_tempo", "ano"), ("dim_tempo", "decada"),
                          ("dim_porte_municipio", "ordem_porte"), ("dim_faixa_valor", "ordem_faixa"),
                          ("dim_componente", "exige_esfera")):
            dims[nome][col] = pd.to_numeric(dims[nome][col]).astype(int)
        cubo_uf = pd.read_sql(text(SQL_CUBO_UF), con)
        lista = ", ".join(f"'{c}'" for c in COMPONENTES_MUNICIPAIS)
        cubo_mun = pd.read_sql(text(SQL_CUBO_MUNICIPIO.format(lista=lista)), con)
    return DadosDW(dims, cubo_uf, cubo_mun, _ler_coordenadas(), "MySQL",
                   f"MySQL conectado ({MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}) | {n:,} linhas na fato"
                   .replace(",", "."))


def carregar_do_snapshot():
    def ler(nome, **kw):
        return pd.read_csv(os.path.join(PASTA_DADOS, nome), **kw)

    dims = {
        "dim_localidade": ler("dim_localidade.csv", dtype={"codigo_ibge": str}),
        "dim_tempo": ler("dim_tempo.csv"),
        "dim_componente": ler("dim_componente.csv"),
        "dim_esfera": ler("dim_esfera.csv"),
        "dim_porte_municipio": ler("dim_porte_municipio.csv"),
        "dim_faixa_valor": ler("dim_faixa_valor.csv"),
    }
    cubo_uf = ler("cubo_uf.csv.gz")
    cubo_mun = ler("cubo_municipio.csv.gz", dtype={"codigo_ibge": str})
    meta = {}
    caminho_meta = os.path.join(PASTA_DADOS, "metadados_snapshot.json")
    if os.path.exists(caminho_meta):
        with open(caminho_meta, encoding="utf-8") as fh:
            meta = json.load(fh)
    detalhe = f"Snapshot do DW (pasta data/, gerado em {meta.get('gerado_em', '?')})"
    return DadosDW(dims, cubo_uf, cubo_mun, _ler_coordenadas(), "Snapshot", detalhe)


def carregar_dados():
    """Carrega o DW conforme DW_FONTE, com fallback automático para o snapshot."""
    if FONTE in ("auto", "mysql"):
        try:
            dados = carregar_do_mysql()
            print(f"[DW] Dados carregados do MySQL: {dados.detalhe}")
            return dados
        except Exception as exc:  # noqa: BLE001
            if FONTE == "mysql":
                raise
            motivo = str(exc).splitlines()[0][:160]
            print("[DW] MySQL não utilizado (normal se o DW ainda não foi carregado no seu computador).")
            print(f"     Motivo técnico: {exc.__class__.__name__}: {motivo}")
            print("     Sem problema: o painel vai usar os dados da pasta data/ (snapshot).")
    dados = carregar_do_snapshot()
    print(f"[DW] {dados.detalhe}")
    return dados
