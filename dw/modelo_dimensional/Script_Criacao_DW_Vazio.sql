-- =====================================================================================
-- DW SNIS — Estrela Única Financeira  (dw_snis_financeiro)  — MySQL 8.0 / InnoDB
-- DDL equivalente ao modelo DW_SNIS_Grupo_2_Estrela_Unica.mwb (Forward Engineering)
-- 1 tabela fato + 6 dimensões | 69 colunas NOT NULL
-- Ordem de criação: dimensões antes da fato (integridade referencial)
-- A CARGA das dimensões e da fato é feita no Pentaho Data Integration.
-- =====================================================================================
CREATE SCHEMA IF NOT EXISTS dw_snis_financeiro DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE dw_snis_financeiro;

-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_localidade (
  sk_localidade   INT          NOT NULL AUTO_INCREMENT,
  codigo_ibge     CHAR(7)      NOT NULL,
  nome_municipio  VARCHAR(120) NOT NULL,
  sigla_uf        CHAR(2)      NOT NULL,
  nome_uf         VARCHAR(30)  NOT NULL,
  nome_regiao     VARCHAR(20)  NOT NULL,
  date_from       DATETIME     NOT NULL,
  date_to         DATETIME     NOT NULL,
  version         INT          NOT NULL,
  PRIMARY KEY (sk_localidade),
  UNIQUE INDEX uq_localidade_codigo_versao (codigo_ibge, version),
  INDEX ix_localidade_uf (sigla_uf),
  INDEX ix_localidade_regiao (nome_regiao)
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_tempo (
  sk_tempo             INT         NOT NULL AUTO_INCREMENT,
  ano                  SMALLINT    NOT NULL,
  rotulo_ano           VARCHAR(4)  NOT NULL,
  seculo               SMALLINT    NOT NULL,
  decada               SMALLINT    NOT NULL,
  trienio_inicio       SMALLINT    NOT NULL,
  quinquenio_inicio    SMALLINT    NOT NULL,
  periodo_plansab      VARCHAR(24) NOT NULL,
  periodo_marco_legal  VARCHAR(24) NOT NULL,
  date_from            DATETIME    NOT NULL,
  date_to              DATETIME    NOT NULL,
  version              INT         NOT NULL,
  PRIMARY KEY (sk_tempo),
  UNIQUE INDEX uq_tempo_ano_versao (ano, version)
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_componente (
  sk_componente      INT          NOT NULL AUTO_INCREMENT,
  codigo_componente  VARCHAR(64)  NOT NULL,
  nome_componente    VARCHAR(100) NOT NULL,
  grupo_financeiro   VARCHAR(20)  NOT NULL,
  papel_analitico    VARCHAR(24)  NOT NULL,
  natureza_valor     VARCHAR(16)  NOT NULL,
  regra_temporal     VARCHAR(24)  NOT NULL,
  exige_esfera       TINYINT      NOT NULL,
  tabela_origem      VARCHAR(40)  NOT NULL,
  regra_agregacao    VARCHAR(255) NOT NULL,
  date_from          DATETIME     NOT NULL,
  date_to            DATETIME     NOT NULL,
  version            INT          NOT NULL,
  PRIMARY KEY (sk_componente),
  UNIQUE INDEX uq_componente_codigo_versao (codigo_componente, version),
  INDEX ix_componente_grupo (grupo_financeiro)
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_esfera (
  sk_esfera         INT          NOT NULL AUTO_INCREMENT,
  codigo_esfera     VARCHAR(20)  NOT NULL,
  nome_esfera       VARCHAR(40)  NOT NULL,
  descricao_esfera  VARCHAR(255) NOT NULL,
  date_from         DATETIME     NOT NULL,
  date_to           DATETIME     NOT NULL,
  version           INT          NOT NULL,
  PRIMARY KEY (sk_esfera),
  UNIQUE INDEX uq_esfera_codigo_versao (codigo_esfera, version)
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_porte_municipio (
  sk_porte_municipio            INT          NOT NULL AUTO_INCREMENT,
  codigo_porte                  VARCHAR(30)  NOT NULL,
  nome_porte                    VARCHAR(60)  NOT NULL,
  faixa_populacional_descricao  VARCHAR(120) NOT NULL,
  ordem_porte                   TINYINT      NOT NULL,
  date_from                     DATETIME     NOT NULL,
  date_to                       DATETIME     NOT NULL,
  version                       INT          NOT NULL,
  PRIMARY KEY (sk_porte_municipio),
  UNIQUE INDEX uq_porte_codigo_versao (codigo_porte, version)
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_faixa_valor (
  sk_faixa_valor      INT           NOT NULL AUTO_INCREMENT,
  codigo_faixa        VARCHAR(30)   NOT NULL,
  nome_faixa          VARCHAR(60)   NOT NULL,
  limite_inferior_rs  DECIMAL(20,2) NOT NULL,
  limite_superior_rs  DECIMAL(20,2) NOT NULL,
  ordem_faixa         TINYINT       NOT NULL,
  date_from           DATETIME      NOT NULL,
  date_to             DATETIME      NOT NULL,
  version             INT           NOT NULL,
  PRIMARY KEY (sk_faixa_valor),
  UNIQUE INDEX uq_faixa_codigo_versao (codigo_faixa, version)
) ENGINE = InnoDB;

-- -------------------------------------------------------------------------------------
-- Tabela fato: PK composta pelas 6 FKs (Slide 15) + UNIQUE protegendo o grão atômico
-- -------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_financeiro_anual (
  sk_localidade                 INT           NOT NULL,
  sk_tempo                      INT           NOT NULL,
  sk_componente                 INT           NOT NULL,
  sk_esfera                     INT           NOT NULL,
  sk_porte_municipio            INT           NOT NULL,
  sk_faixa_valor                INT           NOT NULL,
  valor_informado_rs            DECIMAL(20,2) NOT NULL,
  valor_informado_rs_milhares   DECIMAL(20,4) NOT NULL,
  valor_absoluto_rs             DECIMAL(20,2) NOT NULL,
  quantidade_registros          INT           NOT NULL,
  quantidade_valores_positivos  INT           NOT NULL,
  PRIMARY KEY (sk_localidade, sk_tempo, sk_componente, sk_esfera, sk_porte_municipio, sk_faixa_valor),
  UNIQUE INDEX uq_fato_grao_financeiro (sk_localidade, sk_tempo, sk_componente, sk_esfera),
  INDEX ix_financeiro_sk_tempo (sk_tempo),
  INDEX ix_financeiro_sk_componente (sk_componente),
  INDEX ix_financeiro_sk_esfera (sk_esfera),
  INDEX ix_financeiro_sk_porte_municipio (sk_porte_municipio),
  INDEX ix_financeiro_sk_faixa_valor (sk_faixa_valor),
  CONSTRAINT fk_financeiro_localidade FOREIGN KEY (sk_localidade)
    REFERENCES dim_localidade (sk_localidade) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_financeiro_tempo FOREIGN KEY (sk_tempo)
    REFERENCES dim_tempo (sk_tempo) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_financeiro_componente FOREIGN KEY (sk_componente)
    REFERENCES dim_componente (sk_componente) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_financeiro_esfera FOREIGN KEY (sk_esfera)
    REFERENCES dim_esfera (sk_esfera) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_financeiro_porte_municipio FOREIGN KEY (sk_porte_municipio)
    REFERENCES dim_porte_municipio (sk_porte_municipio) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_financeiro_faixa_valor FOREIGN KEY (sk_faixa_valor)
    REFERENCES dim_faixa_valor (sk_faixa_valor) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;
