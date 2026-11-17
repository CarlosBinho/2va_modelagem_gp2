# DW SNIS — Painel OLAP Financeiro do Saneamento (Plotly Dash)

**UFRPE / DEINFO — Modelagem de Dados — 2ª VA — Grupo 2**
Carlos Jonathan de Lima Malta · Maria Luiza Lima de Oliveira Cordeiro · Emanuel Henrique Silva do Nascimento · Jeferson de Lima Mendes · Edney Cavalcanti dos Santos · Luiz Eduardo Nascimento de Souza · Emanuel Laureano Barros Felipe

Dashboard OLAP em **Python + Plotly Dash** conectado via **SQLAlchemy + PyMySQL** ao Data Warehouse
**`dw_snis_financeiro`** (Estrela Única: `fato_financeiro_anual` + 6 dimensões), seguindo o roteiro da aula
*MD12 — OLAP com Dash*.


**Dashboard online:** https://dw-snis-grupo2.onrender.com/  
*(plano gratuito do Render: o primeiro acesso após um tempo parado pode levar cerca de 1 minuto)*

---

## 1. Estrutura da pasta

```
2va_modelagem_gp2/
├── config_vscode/               # RENOMEIE esta pasta para .vscode (ver passo 1)
│   ├── launch.json              # F5: executa o app.py (modo auto, snapshot ou exportação)
│   └── settings.json            # interpretador do venv
├── variaveis_ambiente.exemplo.txt  # variáveis DW_FONTE / DW_MYSQL_* (opcional)
├── assets/
│   ├── style.css                # tema visual (carregado automaticamente pelo Dash)
│   └── diagrama_estrela.png     # EER da estrela (aba "Modelo Estrela")
├── data/                        # SNAPSHOT do DW (para a nuvem / máquinas sem MySQL)
│   ├── dim_*.csv                # 6 dimensões (versão vigente)
│   ├── cubo_uf.csv.gz           # roll-up Ano × UF × Rubrica × Esfera × Porte × Faixa
│   ├── cubo_municipio.csv.gz    # grão municipal das rubricas de referência
│   ├── aux_coordenadas_municipios.csv  # centroides IBGE (apenas para o mapa)
│   └── metadados_snapshot.json
├── sql/
│   ├── 01_ddl_dw_snis_financeiro.sql   # DDL da estrela (igual ao .mwb)
│   └── 02_consultas_olap_dashboard.sql # consultas OLAP usadas pelo painel
├── ferramentas/
│   └── gerar_snapshot_da_fonte_snis.py # auditoria/snapshot a partir do CSV oficial do SNIS
├── COMO USAR - LEIA PRIMEIRO.pdf # guia passo a passo para quem nunca programou
├── INICIAR_DASHBOARD.bat        # Windows: 2 cliques instalam tudo e abrem o painel
├── iniciar_dashboard_mac_linux.command  # o mesmo para macOS/Linux
├── app.py                       # aplicação Dash (layout + callbacks)
├── dw_dados.py                  # conexão MySQL (SQLAlchemy) e fallback para o snapshot
├── exportar_snapshot_do_dw.py   # MySQL -> data/ (rodar antes de publicar no Render)
├── requirements.txt
├── Procfile                     # deploy no Render.com
├── render.yaml                  # configuração do serviço no Render (Blueprint)
├── dw/                          # artefatos do Data Warehouse (2ª VA)
│   ├── modelo_dimensional/      # .mwb, diagrama, script do DW vazio e dicionário de dados
│   ├── etl_pentaho/             # transformações .ktr (PDI) + carga SQL da dim_tempo
│   └── cubo_psw/                # cubo Mondrian (.xml) do Pentaho Schema Workbench
└── README.md
```

## 2. Fonte dos dados (MySQL ou snapshot)

`dw_dados.py` decide a fonte pela variável `DW_FONTE`:

| `DW_FONTE` | Comportamento |
|---|---|
| `auto` (padrão) | Conecta no MySQL `dw_snis_financeiro`. Se não conectar ou a fato estiver vazia, usa `data/` |
| `mysql` | Exige o MySQL (erro se não conectar) |
| `snapshot` | Usa somente `data/` (modo nuvem) |

O cabeçalho do painel sempre informa qual fonte está ativa. No modo MySQL o **roll-up é executado no
próprio SGBD** (JOIN da fato com as 6 dimensões + `GROUP BY`, ver `sql/02_consultas_olap_dashboard.sql`);
os callbacks do Dash fazem *slice*, *dice* e *drill-down* sobre o cubo retornado.

> A **carga** das dimensões e da fato é feita no **Pentaho Data Integration**. O script
> `ferramentas/gerar_snapshot_da_fonte_snis.py` **não carrega o DW**: ele só gera o snapshot e serve de
> auditoria — reproduz exatamente os números documentados (3.301.298 linhas de fato, 1.835.427 positivos,
> 1.454.952 zeros, 10.919 negativos, 99.067 combinações município-ano). Depois da carga no Pentaho, gere o
> snapshot a partir do próprio DW com `python exportar_snapshot_do_dw.py`.

## 3. Como executar no VS Code (passo a passo da aula)

1. **Abrir a pasta**: *File > Open Folder* → `dashboard`. Renomeie a pasta `config_vscode` para
   **`.vscode`** (assim o F5 e o interpretador do venv ficam pré-configurados).
2. **Extensões**: Python e Pylance (opcional: SQLTools + driver MySQL).
3. **venv**
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # Linux/macOS
   ```
   Se aparecer erro de *Execution_Policies*: PowerShell como Admin → `Set-ExecutionPolicy RemoteSigned`.
   Depois: `Ctrl+Shift+P` → *Python: Select Interpreter* → `venv`.
4. **Dependências**
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
5. **DW no MySQL**: execute `sql/01_ddl_dw_snis_financeiro.sql` no Workbench e rode as transformações de
   carga no **Pentaho** (dimensões primeiro, fato por último).
6. **Conexão** (`dw_dados.py`, bloco *CONFIGURAÇÃO DA CONEXÃO*): troque `MYSQL_PASS` pela sua senha
   (ou defina `DW_MYSQL_PASS`). Porta diferente de 3306 → ajuste `MYSQL_PORT`.
7. **Executar**: `python app.py` ou **F5**. Mensagem no terminal:
   `Servidor Plotly Dash Iniciado com Sucesso! Acesse: http://127.0.0.1:8050`

Sem MySQL disponível o painel abre normalmente com o snapshot (`data/`).

**Jeito fácil (recomendado para a equipe):** dê dois cliques em `INICIAR_DASHBOARD.bat`
(Windows) ou `iniciar_dashboard_mac_linux.command` (Mac). O iniciador:
1. procura um Python 3.10–3.14 (se não houver, abre a página de download e explica o que fazer);
2. cria um ambiente virtual **fora da pasta** (`%LOCALAPPDATA%\DashboardDWSNIS\venv` no Windows,
   `~/.dashboard_dw_snis/venv` no Mac) — assim o Google Drive não sincroniza milhares de arquivos;
3. instala o `requirements.txt` só na primeira vez (ou quando ele mudar);
4. encerra um painel antigo na porta 8050, sobe o servidor e abre o navegador sozinho.

Passo a passo ilustrado para leigos: **`COMO USAR - LEIA PRIMEIRO.pdf`**.

> Não compartilhe a pasta `venv/` nem `__pycache__/`: elas são específicas de cada computador.

> O pacote `cryptography` (no `requirements.txt`) é obrigatório para o PyMySQL autenticar no
> MySQL 8 (`caching_sha2_password`). Sem ele a conexão falha e o painel cai no snapshot.

## 4. O que o painel oferece

**Filtros multidimensionais (barra lateral) — um controle por dimensão**

| Dimensão | Controle |
|---|---|
| `dim_tempo` | `RangeSlider` de anos (1995–2022), `Dropdown` de décadas, período PLANSAB e Novo Marco Legal |
| `dim_localidade` | `Dropdown` de regiões → **callback em cascata** → `Checklist` de UFs (todas marcadas ao escolher a região; botões *Marcar todos* / *Limpar*; desmarcar todas = resultado vazio) |
| `dim_esfera` | `Checklist` Prestador / Município / Estado / Não se aplica |
| `dim_porte_municipio` | `Checklist` das 5 classes de porte |
| `dim_faixa_valor` | `Checklist` das 6 faixas de valor |
| — | Escala dos gráficos (R$ mil / milhões / bilhões) e botão **Redefinir todos os filtros** |

> O DW é anual (o SNIS não tem meses/dias), por isso o recorte temporal usa `RangeSlider` de anos no lugar
> do `DatePickerRange` do exemplo de vendas.

**Abas**

Por desempenho, **somente a aba visível é recalculada** a cada filtro (as demais se atualizam ao
serem abertas): cada interação responde em ~0,2–0,6 s.

1. **Visão Executiva** — 8 KPIs (receita operacional, despesa total, resultado, margem + IN012,
   investimento total, evasão de receitas IN029, saldo de créditos a receber, declarações e % positivas),
   com variação do último ano do recorte; evolução temporal
   (barras + linhas, marcos PLANSAB 2014 e Lei 14.026/2020); cartões por região; barras por UF agrupadas por região.
2. **Composição** — parcelas declaradas de receitas/despesas/investimentos com % sobre o total de
   referência do grupo (e classificação DEX/DTS, destino/origem); drill-down de qualquer das 30 rubricas
   em treemap Brasil ➔ Região ➔ UF e matriz Região × Ano (participação % no total de cada ano).
3. **Investimentos** — investimento por esfera no tempo, origem dos recursos, destino por esfera e
   Novo Marco Legal por região (média anual em janelas de mesma duração: 2017–2019 × 2020–2022).
4. **Porte & Faixa** — finanças por porte, distribuição por faixa, matriz porte × faixa e
   qualidade das declarações ao longo do tempo.
5. **Territorial** — mapa interativo (MapLibre) de bolhas dos municípios, ranking Top N e dispersão multivariada
   (receita × margem × investimento × região) com `RangeSlider` de faixa de margem.
6. **Dados** — tabela paginada e ordenável do cubo filtrado.
7. **Modelo Estrela** — diagrama EER, ficha técnica, grão, métricas e catálogo da `dim_componente`.

**Exportação**: *Exportar CSV* (UTF-8 com BOM, `;` e vírgula decimal — abre certo no Excel) e
*Exportar Excel (.xlsx)* com 3 planilhas (dados filtrados, resumo dos KPIs e filtros aplicados).
**Recarregar DW** relê o MySQL sem reiniciar o servidor.

## 5. Regras de agregação respeitadas

* Indicadores usam sempre rubricas de **referência** (`receita_operacional`, `despesa_total_servico`,
  `investimento_total`, `arrecadacao_total`) — nunca se soma total com parcela (sem dupla contagem).
* `credito_a_receber` é **saldo** (`NAO_SOMAR_ANOS`): o painel mostra apenas o último ano do recorte.
* Destino (água/esgoto/outro) e origem (próprio/oneroso/não oneroso) do investimento ficam em gráficos
  separados, pois são classificações cruzadas do mesmo valor.
* Receitas, despesas e créditos usam a esfera `NAO_SE_APLICA`; desmarcá-la remove essas rubricas do recorte.

## 6. Publicar na nuvem (Render.com)

1. Rode `python exportar_snapshot_do_dw.py` (atualiza `data/` com os números do seu DW).
2. Suba a pasta para um repositório no GitHub (com `data/`, `assets/`, `requirements.txt` e `Procfile`).
3. Render → *New + > Web Service* → selecione o repositório:
   * **Runtime**: Python 3 · **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `gunicorn app:server --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT`
     (ou `python app.py`, como no slide — o app lê a variável `PORT`)
   * **Environment**: `DW_FONTE=snapshot` · **Plan**: Free
4. Entregue o link `https://<nome>.onrender.com` e o link do repositório na planilha da professora.

Teste rápido com túnel (só enquanto o VS Code estiver aberto): `npx localtunnel --port 8050`.
