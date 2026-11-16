-- =====================================================================================
-- Carga da Dimensão Tempo (dim_tempo) — dw_snis_financeiro
-- Conforme orientação da disciplina, a dimensão de data/tempo é carregada em SQL
-- (executar no MySQL Workbench ANTES da transformação FatoFinanceiroAnual.ktr).
-- Grão anual: o SNIS é declarado por ano, portanto não há meses ou dias artificiais.
-- Linha de chave zero (sk_tempo = 0) para referências desconhecidas, como na aula.
-- =====================================================================================
USE dw_snis_financeiro;

SET @OLD_SQL_MODE = @@SQL_MODE;
SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';   -- permite inserir o valor zero na chave AUTO_INCREMENT
SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM dim_tempo WHERE sk_tempo >= 0;
SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO dim_tempo
  (sk_tempo, ano, rotulo_ano, seculo, decada, trienio_inicio, quinquenio_inicio,
   periodo_plansab, periodo_marco_legal, date_from, date_to, version)
VALUES
  (0, 0, 'N/A', 0, 0, 0, 0, 'N/A', 'N/A', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (1, 1995, '1995', 20, 1990, 1995, 1995, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (2, 1996, '1996', 20, 1990, 1995, 1995, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (3, 1997, '1997', 20, 1990, 1995, 1995, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (4, 1998, '1998', 20, 1990, 1998, 1995, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (5, 1999, '1999', 20, 1990, 1998, 1995, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (6, 2000, '2000', 20, 2000, 1998, 2000, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (7, 2001, '2001', 21, 2000, 2001, 2000, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (8, 2002, '2002', 21, 2000, 2001, 2000, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (9, 2003, '2003', 21, 2000, 2001, 2000, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (10, 2004, '2004', 21, 2000, 2004, 2000, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (11, 2005, '2005', 21, 2000, 2004, 2005, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (12, 2006, '2006', 21, 2000, 2004, 2005, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (13, 2007, '2007', 21, 2000, 2007, 2005, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (14, 2008, '2008', 21, 2000, 2007, 2005, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (15, 2009, '2009', 21, 2000, 2007, 2005, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (16, 2010, '2010', 21, 2010, 2010, 2010, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (17, 2011, '2011', 21, 2010, 2010, 2010, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (18, 2012, '2012', 21, 2010, 2010, 2010, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (19, 2013, '2013', 21, 2010, 2013, 2010, 'PRE_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (20, 2014, '2014', 21, 2010, 2013, 2010, 'VIGENCIA_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (21, 2015, '2015', 21, 2010, 2013, 2015, 'VIGENCIA_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (22, 2016, '2016', 21, 2010, 2016, 2015, 'VIGENCIA_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (23, 2017, '2017', 21, 2010, 2016, 2015, 'VIGENCIA_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (24, 2018, '2018', 21, 2010, 2016, 2015, 'VIGENCIA_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (25, 2019, '2019', 21, 2010, 2019, 2015, 'VIGENCIA_PLANSAB', 'PRE_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (26, 2020, '2020', 21, 2020, 2019, 2020, 'VIGENCIA_PLANSAB', 'POS_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (27, 2021, '2021', 21, 2020, 2019, 2020, 'VIGENCIA_PLANSAB', 'POS_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1),
  (28, 2022, '2022', 21, 2020, 2022, 2020, 'VIGENCIA_PLANSAB', 'POS_MARCO_LEGAL', '1970-01-01 00:00:01', '2038-01-01 00:00:00', 1);

SET SQL_MODE = @OLD_SQL_MODE;

-- Conferência: 29 linhas (28 anos de 1995 a 2022 + chave zero)
SELECT COUNT(*) AS linhas, MIN(NULLIF(ano, 0)) AS primeiro_ano, MAX(ano) AS ultimo_ano FROM dim_tempo;
