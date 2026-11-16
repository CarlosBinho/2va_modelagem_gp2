"""
Exporta o SNAPSHOT do dashboard (pasta data/) a partir do Data Warehouse MySQL
dw_snis_financeiro, já carregado pelo Pentaho Data Integration.

Use antes de publicar no Render (onde não há MySQL): o dashboard na nuvem passa a
mostrar exatamente os números do seu DW.

    python exportar_snapshot_do_dw.py
"""
import json
import os
from datetime import datetime

import dw_dados


def main():
    dados = dw_dados.carregar_do_mysql()
    pasta = dw_dados.PASTA_DADOS
    os.makedirs(pasta, exist_ok=True)

    dados.dim_localidade.to_csv(os.path.join(pasta, "dim_localidade.csv"), index=False)
    dados.dim_tempo.to_csv(os.path.join(pasta, "dim_tempo.csv"), index=False)
    dados.dim_componente.to_csv(os.path.join(pasta, "dim_componente.csv"), index=False)
    dados.dim_esfera.to_csv(os.path.join(pasta, "dim_esfera.csv"), index=False)
    dados.dim_porte.to_csv(os.path.join(pasta, "dim_porte_municipio.csv"), index=False)
    dados.dim_faixa.to_csv(os.path.join(pasta, "dim_faixa_valor.csv"), index=False)

    cols_uf = ["ano", "sigla_uf", "componente", "esfera", "porte", "faixa", "valor_informado_rs",
               "valor_absoluto_rs", "quantidade_registros", "quantidade_valores_positivos"]
    dados.cubo_uf[cols_uf].to_csv(os.path.join(pasta, "cubo_uf.csv.gz"), index=False,
                                  float_format="%.2f")
    cols_mun = ["ano", "codigo_ibge", "componente", "esfera", "porte", "faixa", "valor_informado_rs"]
    dados.cubo_mun[cols_mun].to_csv(os.path.join(pasta, "cubo_municipio.csv.gz"), index=False,
                                    float_format="%.2f")

    meta = {
        "origem": f"Exportado do MySQL {dw_dados.MYSQL_HOST}:{dw_dados.MYSQL_PORT}/{dw_dados.MYSQL_DB}",
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "linhas_fato_representadas": dados.total_linhas_fato,
        "linhas_cubo_uf": int(len(dados.cubo_uf)),
        "linhas_cubo_municipio": int(len(dados.cubo_mun)),
    }
    with open(os.path.join(pasta, "metadados_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print("Snapshot exportado com sucesso:")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
