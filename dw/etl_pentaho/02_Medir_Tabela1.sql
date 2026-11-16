-- Rode no MySQL Workbench DEPOIS de carregar todo o DW.
-- Mostra colunas, linhas e tamanho de cada tabela para preencher a Tabela 1 do artigo.
USE dw_snis_financeiro;
ANALYZE TABLE dim_localidade, dim_tempo, dim_componente, dim_esfera,
              dim_porte_municipio, dim_faixa_valor, fato_financeiro_anual;

SELECT t.table_name                                       AS tabela,
       (SELECT COUNT(*) FROM information_schema.columns c
         WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) AS colunas,
       t.table_rows                                       AS linhas_estimadas,
       ROUND((t.data_length + t.index_length) / 1024, 1)        AS tamanho_kb,
       ROUND((t.data_length + t.index_length) / 1024 / 1024, 2) AS tamanho_mb
FROM information_schema.tables t
WHERE t.table_schema = 'dw_snis_financeiro'
ORDER BY t.table_name;

-- Contagem exata de linhas (table_rows acima é estimativa do InnoDB):
SELECT 'dim_localidade' tabela, COUNT(*) linhas FROM dim_localidade UNION ALL
SELECT 'dim_tempo', COUNT(*) FROM dim_tempo UNION ALL
SELECT 'dim_componente', COUNT(*) FROM dim_componente UNION ALL
SELECT 'dim_esfera', COUNT(*) FROM dim_esfera UNION ALL
SELECT 'dim_porte_municipio', COUNT(*) FROM dim_porte_municipio UNION ALL
SELECT 'dim_faixa_valor', COUNT(*) FROM dim_faixa_valor UNION ALL
SELECT 'fato_financeiro_anual', COUNT(*) FROM fato_financeiro_anual;
-- Esperado: 5550, 29, 31, 5, 6, 7 e 3301298.
