"""
Gera o SNAPSHOT do DW (pasta data/) diretamente a partir do arquivo oficial do SNIS,
aplicando EXATAMENTE as mesmas regras de transformação documentadas para o ETL
do dw_snis_financeiro (00_LEIA_PRIMEIRO.md e 02_DICIONARIO.md).

IMPORTANTE
----------
* Este script NÃO carrega o Data Warehouse. A carga oficial das dimensões e da
  fato é feita no Pentaho Data Integration (exigência da disciplina).
* Ele existe apenas para que o dashboard funcione na nuvem (Render) e em máquinas
  sem MySQL, e para auditar os números (as contagens batem 1:1 com a documentação:
  3.301.298 linhas de fato, 1.835.427 positivos, 1.454.952 zeros, 10.919 negativos).
* Depois que o DW estiver carregado pelo Pentaho, prefira gerar o snapshot a partir
  do próprio MySQL com:  python exportar_snapshot_do_dw.py

Uso:
    python ferramentas/gerar_snapshot_da_fonte_snis.py \
        --snis  caminho/br_mdr_snis_municipio_agua_esgoto.csv.gz \
        --municipios caminho/br_bd_diretorios_brasil_municipio.csv.gz \
        --componentes caminho/03_CATALOGO_COMPONENTES.csv
"""
import argparse
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(AQUI, "..", "data")

# Rubricas exportadas no cubo municipal (ranking, mapa e dispersão)
COMPONENTES_MUNICIPAIS = [
    "receita_operacional", "despesa_total_servico", "despesa_exploracao",
    "investimento_total", "arrecadacao_total", "credito_a_receber",
]


def dim_tempo(anos):
    linhas = []
    for a in sorted(anos):
        linhas.append({
            "ano": a, "rotulo_ano": str(a),
            "seculo": 20 if a <= 2000 else 21,
            "decada": (a // 10) * 10,
            "trienio_inicio": 1995 + ((a - 1995) // 3) * 3,
            "quinquenio_inicio": (a // 5) * 5,
            "periodo_plansab": "PRE_PLANSAB" if a <= 2013 else "VIGENCIA_PLANSAB",
            "periodo_marco_legal": "PRE_MARCO_LEGAL" if a <= 2019 else "POS_MARCO_LEGAL",
        })
    return pd.DataFrame(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snis", required=True)
    ap.add_argument("--municipios", required=True)
    ap.add_argument("--componentes", required=True)
    args = ap.parse_args()
    os.makedirs(DESTINO, exist_ok=True)

    cat = pd.read_csv(args.componentes, encoding="utf-8-sig")

    # 46 colunas monetárias -> (codigo_componente, codigo_esfera)
    mapa = {}
    for c in cat.itertuples():
        if int(c.exige_esfera) == 1:
            for e in ("prestador", "municipio", "estado"):
                mapa[f"{c.codigo_componente}_{e}"] = (c.codigo_componente, e.upper())
        else:
            col = "credito_areceber" if c.codigo_componente == "credito_a_receber" else c.codigo_componente
            mapa[col] = (c.codigo_componente, "NAO_SE_APLICA")
    assert len(mapa) == 46, len(mapa)

    usar = ["ano", "id_municipio", "sigla_uf", "populacao_urbana"] + list(mapa)
    bruto = pd.read_csv(args.snis, usecols=usar, dtype={"id_municipio": str})

    # Fato esparso: só células efetivamente informadas viram linha (ausência != zero)
    fato = bruto.melt(id_vars=["ano", "id_municipio", "sigla_uf", "populacao_urbana"],
                      value_vars=list(mapa), var_name="coluna", value_name="valor")
    fato = fato.dropna(subset=["valor"])
    fato["componente"] = fato["coluna"].map(lambda x: mapa[x][0])
    fato["esfera"] = fato["coluna"].map(lambda x: mapa[x][1])
    fato["valor"] = fato["valor"].round(2)

    pu = fato["populacao_urbana"]
    fato["porte"] = np.select(
        [pu.isna(), pu <= 20000, pu <= 100000, pu <= 900000],
        ["NAO_INFORMADO", "PEQUENO", "MEDIO", "GRANDE"], "METROPOLE")
    v = fato["valor"]
    fato["faixa"] = np.select(
        [v < 0, v == 0, v <= 1e5, v <= 1e6, v <= 1e7],
        ["VALOR_NEGATIVO", "VALOR_ZERADO", "FAIXA_ATE_100K", "FAIXA_100K_1M", "FAIXA_1M_10M"],
        "FAIXA_ACIMA_10M")
    fato["valor_absoluto_rs"] = v.abs()
    fato["quantidade_registros"] = 1
    fato["quantidade_valores_positivos"] = (v > 0).astype(int)

    # ---------------- Dimensões -----------------
    mun = pd.read_csv(args.municipios, dtype={"id_municipio": str})
    mun = mun[mun["id_municipio"].isin(fato["id_municipio"].unique())]
    loc = mun.rename(columns={"id_municipio": "codigo_ibge", "nome": "nome_municipio"})[
        ["codigo_ibge", "nome_municipio", "sigla_uf", "nome_uf", "nome_regiao"]]
    loc.sort_values("codigo_ibge").to_csv(os.path.join(DESTINO, "dim_localidade.csv"), index=False)

    coords = mun["centroide"].str.extract(r"POINT\(([-\d\.]+) ([-\d\.]+)\)").astype(float)
    pd.DataFrame({"codigo_ibge": mun["id_municipio"], "longitude": coords[0].round(4),
                  "latitude": coords[1].round(4)}).to_csv(
        os.path.join(DESTINO, "aux_coordenadas_municipios.csv"), index=False)

    dim_tempo(fato["ano"].unique()).to_csv(os.path.join(DESTINO, "dim_tempo.csv"), index=False)
    cat.to_csv(os.path.join(DESTINO, "dim_componente.csv"), index=False)

    # ---------------- Cubos -----------------
    cubo_uf = fato.groupby(["ano", "sigla_uf", "componente", "esfera", "porte", "faixa"],
                           as_index=False).agg(
        valor_informado_rs=("valor", "sum"),
        valor_absoluto_rs=("valor_absoluto_rs", "sum"),
        quantidade_registros=("quantidade_registros", "sum"),
        quantidade_valores_positivos=("quantidade_valores_positivos", "sum"))
    cubo_uf.to_csv(os.path.join(DESTINO, "cubo_uf.csv.gz"), index=False, float_format="%.2f")

    cubo_mun = fato[fato["componente"].isin(COMPONENTES_MUNICIPAIS)][
        ["ano", "id_municipio", "componente", "esfera", "porte", "faixa", "valor"]].rename(
        columns={"id_municipio": "codigo_ibge", "valor": "valor_informado_rs"})
    cubo_mun.to_csv(os.path.join(DESTINO, "cubo_municipio.csv.gz"), index=False, float_format="%.2f")

    meta = {
        "origem": "Snapshot gerado a partir do arquivo oficial do SNIS com as regras do ETL do dw_snis_financeiro",
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "linhas_fato_representadas": int(len(fato)),
        "valores_positivos": int((v > 0).sum()),
        "valores_zerados": int((v == 0).sum()),
        "valores_negativos": int((v < 0).sum()),
        "combinacoes_municipio_ano": int(fato.groupby(["id_municipio", "ano"]).ngroups),
        "linhas_cubo_uf": int(len(cubo_uf)),
        "linhas_cubo_municipio": int(len(cubo_mun)),
    }
    with open(os.path.join(DESTINO, "metadados_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
