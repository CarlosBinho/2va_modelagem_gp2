-- =====================================================================================
-- Consultas OLAP utilizadas pelo dashboard (dw_dados.py) — dw_snis_financeiro
-- O MySQL executa o ROLL-UP (JOIN estrela + GROUP BY); o Dash faz SLICE/DICE/DRILL
-- em memória a cada interação do usuário.
-- =====================================================================================
USE dw_snis_financeiro;

-- 1) CUBO POR UF  (Ano × UF × Rubrica × Esfera × Porte × Faixa)  -> abas Executiva,
--    Composição, Investimentos, Porte & Faixa, Dados Detalhados e exportações
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
GROUP BY t.ano, l.sigla_uf, c.codigo_componente, e.codigo_esfera, p.codigo_porte, fv.codigo_faixa;

-- 2) CUBO MUNICIPAL (grão atômico) para as rubricas de referência -> aba Territorial
SELECT  t.ano, l.codigo_ibge,
        c.codigo_componente AS componente, e.codigo_esfera AS esfera,
        p.codigo_porte AS porte, fv.codigo_faixa AS faixa,
        f.valor_informado_rs
FROM fato_financeiro_anual f
JOIN dim_tempo           t  ON t.sk_tempo            = f.sk_tempo
JOIN dim_localidade      l  ON l.sk_localidade       = f.sk_localidade
JOIN dim_componente      c  ON c.sk_componente       = f.sk_componente
JOIN dim_esfera          e  ON e.sk_esfera           = f.sk_esfera
JOIN dim_porte_municipio p  ON p.sk_porte_municipio  = f.sk_porte_municipio
JOIN dim_faixa_valor     fv ON fv.sk_faixa_valor     = f.sk_faixa_valor
WHERE c.codigo_componente IN ('receita_operacional', 'despesa_total_servico', 'despesa_exploracao',
                              'investimento_total', 'arrecadacao_total', 'credito_a_receber');

-- 3) Exemplos dos indicadores (KPIs) exibidos no painel, para conferência no Workbench
-- 3.1 Receita, despesa, resultado e margem operacional (Brasil, 2018–2022)
SELECT  SUM(CASE WHEN c.codigo_componente = 'receita_operacional'   THEN f.valor_informado_rs END) AS receita,
        SUM(CASE WHEN c.codigo_componente = 'despesa_total_servico' THEN f.valor_informado_rs END) AS despesa,
        SUM(CASE WHEN c.codigo_componente = 'receita_operacional'   THEN f.valor_informado_rs END)
      - SUM(CASE WHEN c.codigo_componente = 'despesa_total_servico' THEN f.valor_informado_rs END) AS resultado
FROM fato_financeiro_anual f
JOIN dim_componente c ON c.sk_componente = f.sk_componente
JOIN dim_tempo      t ON t.sk_tempo      = f.sk_tempo
WHERE t.ano BETWEEN 2018 AND 2022;

-- 3.2 Créditos a receber: métrica SEMI-ADITIVA (saldo) — somar só dentro do mesmo ano
SELECT  t.ano, l.nome_regiao, SUM(f.valor_informado_rs) AS saldo_credito_a_receber
FROM fato_financeiro_anual f
JOIN dim_componente c ON c.sk_componente = f.sk_componente
JOIN dim_tempo      t ON t.sk_tempo      = f.sk_tempo
JOIN dim_localidade l ON l.sk_localidade = f.sk_localidade
WHERE c.codigo_componente = 'credito_a_receber'
GROUP BY t.ano, l.nome_regiao
ORDER BY t.ano, l.nome_regiao;

-- 3.3 Investimento total por esfera antes/depois do Novo Marco Legal (média anual)
SELECT  l.nome_regiao, t.periodo_marco_legal, e.nome_esfera,
        SUM(f.valor_informado_rs) / COUNT(DISTINCT t.ano) AS media_anual_investimento
FROM fato_financeiro_anual f
JOIN dim_componente c ON c.sk_componente = f.sk_componente
JOIN dim_tempo      t ON t.sk_tempo      = f.sk_tempo
JOIN dim_localidade l ON l.sk_localidade = f.sk_localidade
JOIN dim_esfera     e ON e.sk_esfera     = f.sk_esfera
WHERE c.codigo_componente = 'investimento_total'
GROUP BY l.nome_regiao, t.periodo_marco_legal, e.nome_esfera;

-- 3.4 Distribuição das declarações por porte × faixa de valor
SELECT  p.nome_porte, fv.nome_faixa,
        SUM(f.quantidade_registros)         AS declaracoes,
        SUM(f.quantidade_valores_positivos) AS declaracoes_positivas
FROM fato_financeiro_anual f
JOIN dim_porte_municipio p  ON p.sk_porte_municipio = f.sk_porte_municipio
JOIN dim_faixa_valor     fv ON fv.sk_faixa_valor    = f.sk_faixa_valor
GROUP BY p.ordem_porte, p.nome_porte, fv.ordem_faixa, fv.nome_faixa
ORDER BY p.ordem_porte, fv.ordem_faixa;
