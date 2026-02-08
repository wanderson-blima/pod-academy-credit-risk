"""
Book de Variaveis — Faturamento.

Gera ~108 variaveis comportamentais de faturamento para o modelo de credit risk,
agregadas por NUM_CPF + SAFRA. Enriquece dados transacionais de faturamento com
dimensoes (plataforma, tipo_faturamento) e calcula metricas de volumetria,
valores financeiros, pivots por plataforma/indicadores, taxas e score de risco.

IMPORTANTE: Este book NAO faz JOIN com dados_cadastrais para evitar data leakage
(Story TD-1.1 — FAT_VLR_FPD era copia direta do target FPD).

Inputs:
    - Silver.rawdata.dados_faturamento (fato)
    - Silver.rawdata.plataforma (dimensao)
    - Silver.rawdata.tipo_faturamento (dimensao)

Outputs:
    - Silver.book.faturamento (~108 variaveis, particionado por SAFRA)

Uso:
    from book_faturamento import build_book_faturamento
    results = build_book_faturamento(spark, safras=[202410, 202411])
"""

from datetime import date
import logging

import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    SILVER_BASE, PATH_BOOK_FATURAMENTO, SAFRAS as DEFAULT_SAFRAS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("book_faturamento")

# =============================================================================
# PATHS
# =============================================================================
_RAWDATA = f"{SILVER_BASE}/Tables/rawdata"

PATH_FATURAMENTO = f"{_RAWDATA}/dados_faturamento"
PATH_PLATAFORMA = f"{_RAWDATA}/plataforma"
PATH_TIPO_FATURAMENTO = f"{_RAWDATA}/tipo_faturamento"
PATH_OUTPUT = PATH_BOOK_FATURAMENTO

# =============================================================================
# SQL TEMPLATE (~108 variaveis — SEM dados_cadastrais, SEM FAT_VLR_FPD)
# =============================================================================
SQL_TEMPLATE = """
WITH base_enrich AS (
    SELECT
        f.NUM_CPF,
        CAST('{safra}' AS INT) AS SAFRA,
        f.CONTRATO, f.DAT_REFERENCIA, f.DAT_CRIACAO_FAT,
        f.DAT_VENCIMENTO_FAT, f.DAT_STATUS_FAT, f.DAT_ATIVACAO_CONTA_CLI,
        COALESCE(f.VAL_FAT_BRUTO, 0) AS VAL_FAT_BRUTO,
        COALESCE(f.VAL_FAT_LIQUIDO, 0) AS VAL_FAT_LIQUIDO,
        COALESCE(f.VAL_FAT_CREDITO, 0) AS VAL_FAT_CREDITO,
        COALESCE(f.VAL_FAT_ABERTO, 0) AS VAL_FAT_ABERTO,
        COALESCE(f.VAL_FAT_ABERTO_LIQ, 0) AS VAL_FAT_ABERTO_LIQ,
        COALESCE(f.VAL_FAT_AJUSTE, 0) AS VAL_FAT_AJUSTE,
        COALESCE(f.VAL_FAT_BRUTO_BC, 0) AS VAL_FAT_BRUTO_BC,
        COALESCE(f.VAL_FAT_PAGAMENTO_BRUTO, 0) AS VAL_FAT_PAGAMENTO_BRUTO,
        COALESCE(f.VAL_FAT_LIQ_JM_MC, 0) AS VAL_FAT_LIQ_JM_MC,
        COALESCE(f.VAL_MULTA_JUROS, 0) AS VAL_MULTA_JUROS,
        COALESCE(f.VAL_MULTA_CANCELAMENTO, 0) AS VAL_MULTA_CANCELAMENTO,
        COALESCE(f.VAL_PARC_APARELHO_LIQ, 0) AS VAL_PARC_APARELHO_LIQ,
        f.IND_WO, f.IND_PDD, f.IND_PCCR, f.IND_ACA,
        f.IND_PRIMEIRA_FAT, f.IND_FRAUDE, f.IND_ISENCAO_COB_FAT,
        f.COD_PLATAFORMA,
        p.DSC_GRUPO_PLATAFORMA, p.COD_GRUPO_PLATAFORMA_BI,
        t.DSC_TIPO_FATURAMENTO
    FROM fato_faturamento f
    LEFT JOIN dim_plataforma p ON f.COD_PLATAFORMA = p.COD_PLATAFORMA
    LEFT JOIN dim_tipo_faturamento t ON f.DW_TIPO_FATURAMENTO = t.DW_TIPO_FATURAMENTO
    WHERE f.DAT_REFERENCIA < '{data_cutoff}'
),
agregado AS (
    SELECT
        NUM_CPF, SAFRA,
        COUNT(*) AS QTD_FATURAS,
        COUNT(DISTINCT CONTRATO) AS QTD_CONTRATOS_DISTINTOS,
        COUNT(DISTINCT DAT_REFERENCIA) AS QTD_SAFRAS_DISTINTAS,
        SUM(CASE WHEN IND_PRIMEIRA_FAT = 'S' THEN 1 ELSE 0 END) AS QTD_FATURAS_PRIMEIRA,
        SUM(CASE WHEN IND_WO = 'W' THEN 1 ELSE 0 END) AS QTD_FATURAS_WO,
        SUM(CASE WHEN IND_WO = 'R' THEN 1 ELSE 0 END) AS QTD_FATURAS_REGULAR,
        SUM(CASE WHEN IND_PDD = 'S' THEN 1 ELSE 0 END) AS QTD_FATURAS_PDD,
        SUM(CASE WHEN IND_PDD = 'N' THEN 1 ELSE 0 END) AS QTD_FATURAS_SEM_PDD,
        SUM(CASE WHEN IND_PCCR = 'C' THEN 1 ELSE 0 END) AS QTD_FATURAS_PCCR_C,
        SUM(CASE WHEN IND_PCCR = 'W' THEN 1 ELSE 0 END) AS QTD_FATURAS_PCCR_W,
        SUM(CASE WHEN IND_ACA = 'S' THEN 1 ELSE 0 END) AS QTD_FATURAS_ACA,
        SUM(CASE WHEN IND_ACA = 'N' THEN 1 ELSE 0 END) AS QTD_FATURAS_SEM_ACA,
        SUM(CASE WHEN IND_FRAUDE = 'S' THEN 1 ELSE 0 END) AS QTD_FATURAS_FRAUDE,
        SUM(CASE WHEN IND_ISENCAO_COB_FAT IN ('Y','S') THEN 1 ELSE 0 END) AS QTD_FATURAS_ISENTAS,
        SUM(CASE WHEN IND_ISENCAO_COB_FAT = 'N' THEN 1 ELSE 0 END) AS QTD_FATURAS_NAO_ISENTAS,
        SUM(VAL_FAT_BRUTO) AS VLR_FAT_BRUTO_TOTAL,
        AVG(VAL_FAT_BRUTO) AS VLR_FAT_BRUTO_MEDIO,
        MAX(VAL_FAT_BRUTO) AS VLR_FAT_BRUTO_MAX,
        MIN(VAL_FAT_BRUTO) AS VLR_FAT_BRUTO_MIN,
        STDDEV(VAL_FAT_BRUTO) AS VLR_FAT_BRUTO_STDDEV,
        SUM(VAL_FAT_LIQUIDO) AS VLR_FAT_LIQUIDO_TOTAL,
        AVG(VAL_FAT_LIQUIDO) AS VLR_FAT_LIQUIDO_MEDIO,
        MAX(VAL_FAT_LIQUIDO) AS VLR_FAT_LIQUIDO_MAX,
        SUM(VAL_FAT_CREDITO) AS VLR_FAT_CREDITO_TOTAL,
        AVG(VAL_FAT_CREDITO) AS VLR_FAT_CREDITO_MEDIO,
        MAX(VAL_FAT_CREDITO) AS VLR_FAT_CREDITO_MAX,
        SUM(VAL_FAT_ABERTO) AS VLR_FAT_ABERTO_TOTAL,
        AVG(VAL_FAT_ABERTO) AS VLR_FAT_ABERTO_MEDIO,
        MAX(VAL_FAT_ABERTO) AS VLR_FAT_ABERTO_MAX,
        SUM(VAL_FAT_ABERTO_LIQ) AS VLR_FAT_ABERTO_LIQ_TOTAL,
        AVG(VAL_FAT_ABERTO_LIQ) AS VLR_FAT_ABERTO_LIQ_MEDIO,
        SUM(VAL_MULTA_JUROS) AS VLR_MULTA_JUROS_TOTAL,
        AVG(VAL_MULTA_JUROS) AS VLR_MULTA_JUROS_MEDIO,
        MAX(VAL_MULTA_JUROS) AS VLR_MULTA_JUROS_MAX,
        SUM(VAL_MULTA_CANCELAMENTO) AS VLR_MULTA_CANCEL_TOTAL,
        AVG(VAL_MULTA_CANCELAMENTO) AS VLR_MULTA_CANCEL_MEDIO,
        SUM(VAL_FAT_AJUSTE) AS VLR_FAT_AJUSTE_TOTAL,
        SUM(VAL_FAT_PAGAMENTO_BRUTO) AS VLR_FAT_PAGAMENTO_BRUTO_TOTAL,
        SUM(VAL_PARC_APARELHO_LIQ) AS VLR_PARC_APARELHO_TOTAL,
        SUM(VAL_FAT_LIQ_JM_MC) AS VLR_FAT_LIQ_JM_MC_TOTAL,
        SUM(CASE WHEN COD_PLATAFORMA = 'AUTOC' THEN 1 ELSE 0 END) AS QTD_FAT_AUTOC,
        SUM(CASE WHEN COD_PLATAFORMA = 'AUTOC' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_AUTOC,
        SUM(CASE WHEN COD_PLATAFORMA = 'POSPG' THEN 1 ELSE 0 END) AS QTD_FAT_POSPG,
        SUM(CASE WHEN COD_PLATAFORMA = 'POSPG' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_POSPG,
        SUM(CASE WHEN COD_PLATAFORMA = 'PREPG' THEN 1 ELSE 0 END) AS QTD_FAT_PREPG,
        SUM(CASE WHEN COD_PLATAFORMA = 'PREPG' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_PREPG,
        SUM(CASE WHEN COD_PLATAFORMA = 'POSBL' THEN 1 ELSE 0 END) AS QTD_FAT_POSBL,
        SUM(CASE WHEN COD_PLATAFORMA = 'POSBL' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_POSBL,
        SUM(CASE WHEN COD_PLATAFORMA = '-2' THEN 1 ELSE 0 END) AS QTD_FAT_SEM_PLATAFORMA,
        SUM(CASE WHEN COD_PLATAFORMA = '-2' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_SEM_PLATAFORMA,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Pós Pago' THEN 1 ELSE 0 END) AS QTD_FAT_POS_PAGO,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Pós Pago' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_POS_PAGO,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Pré Pago' THEN 1 ELSE 0 END) AS QTD_FAT_PRE_PAGO,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Pré Pago' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_PRE_PAGO,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Controle' THEN 1 ELSE 0 END) AS QTD_FAT_CONTROLE,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Controle' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_CONTROLE,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Telemetria' THEN 1 ELSE 0 END) AS QTD_FAT_TELEMETRIA,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Telemetria' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_TELEMETRIA,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Outros' THEN 1 ELSE 0 END) AS QTD_FAT_OUTROS,
        SUM(CASE WHEN DSC_GRUPO_PLATAFORMA = 'Outros' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_OUTROS,
        SUM(CASE WHEN IND_WO = 'W' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_WO,
        SUM(CASE WHEN IND_WO = 'R' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_REGULAR,
        SUM(CASE WHEN IND_PDD = 'S' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_PDD,
        SUM(CASE WHEN IND_PDD = 'N' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_SEM_PDD,
        SUM(CASE WHEN IND_ACA = 'S' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_ACA,
        SUM(CASE WHEN IND_FRAUDE = 'S' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_FAT_FRAUDE,
        SUM(CASE WHEN IND_PRIMEIRA_FAT = 'S' THEN VAL_FAT_LIQUIDO ELSE 0 END) AS VLR_PRIMEIRA_FAT,
        AVG(CASE WHEN IND_WO = 'W' THEN VAL_FAT_LIQUIDO END) AS VLR_MEDIO_WO,
        AVG(CASE WHEN IND_PDD = 'S' THEN VAL_FAT_LIQUIDO END) AS VLR_MEDIO_PDD,
        AVG(CASE WHEN IND_PRIMEIRA_FAT = 'S' THEN VAL_FAT_LIQUIDO END) AS VLR_MEDIO_PRIMEIRA_FAT,
        MAX(CASE WHEN IND_WO = 'W' THEN VAL_FAT_LIQUIDO END) AS VLR_MAX_WO,
        MAX(CASE WHEN IND_PDD = 'S' THEN VAL_FAT_LIQUIDO END) AS VLR_MAX_PDD,
        DATEDIFF(TO_DATE('{data_cutoff}'), MIN(DAT_CRIACAO_FAT)) AS DIAS_DESDE_PRIMEIRA_FAT,
        DATEDIFF(TO_DATE('{data_cutoff}'), MAX(DAT_CRIACAO_FAT)) AS DIAS_DESDE_ULTIMA_FAT,
        DATEDIFF(MAX(DAT_CRIACAO_FAT), MIN(DAT_CRIACAO_FAT)) AS DIAS_ENTRE_PRIMEIRA_ULTIMA_FAT,
        DATEDIFF(TO_DATE('{data_cutoff}'), MIN(DAT_ATIVACAO_CONTA_CLI)) AS DIAS_DESDE_ATIVACAO_CONTA,
        AVG(DATEDIFF(DAT_VENCIMENTO_FAT, DAT_CRIACAO_FAT)) AS DIAS_MEDIO_CRIACAO_VENCIMENTO,
        MAX(DATEDIFF(DAT_VENCIMENTO_FAT, DAT_CRIACAO_FAT)) AS DIAS_MAX_CRIACAO_VENCIMENTO,
        MIN(DATEDIFF(DAT_VENCIMENTO_FAT, DAT_CRIACAO_FAT)) AS DIAS_MIN_CRIACAO_VENCIMENTO,
        AVG(DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT)) AS DIAS_ATRASO_MEDIO,
        MAX(DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT)) AS DIAS_ATRASO_MAX,
        MIN(DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT)) AS DIAS_ATRASO_MIN,
        SUM(CASE WHEN DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT) > 0 THEN 1 ELSE 0 END) AS QTD_FATURAS_ATRASADAS,
        SUM(CASE WHEN DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT) > 30 THEN 1 ELSE 0 END) AS QTD_FATURAS_ATRASO_30D,
        SUM(CASE WHEN DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT) > 60 THEN 1 ELSE 0 END) AS QTD_FATURAS_ATRASO_60D,
        SUM(CASE WHEN DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT) > 90 THEN 1 ELSE 0 END) AS QTD_FATURAS_ATRASO_90D,
        SUM(CASE WHEN DATEDIFF(DAT_STATUS_FAT, DAT_VENCIMENTO_FAT) <= 0 THEN 1 ELSE 0 END) AS QTD_FATURAS_EM_DIA
    FROM base_enrich
    GROUP BY NUM_CPF, SAFRA
)
SELECT
    a.*,
    ROUND(a.QTD_FATURAS_WO / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_WO,
    ROUND(a.QTD_FATURAS_PDD / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_PDD,
    ROUND(a.QTD_FATURAS_ACA / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_ACA,
    ROUND(a.QTD_FATURAS_FRAUDE / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_FRAUDE,
    ROUND(a.QTD_FATURAS_PRIMEIRA / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_PRIMEIRA_FAT,
    ROUND(a.QTD_FATURAS_ISENTAS / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_ISENCAO,
    ROUND(a.QTD_FATURAS_ATRASADAS / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_ATRASO,
    ROUND(a.QTD_FATURAS_ATRASO_30D / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_ATRASO_30D,
    ROUND(a.QTD_FATURAS_ATRASO_60D / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_ATRASO_60D,
    ROUND(a.QTD_FATURAS_ATRASO_90D / NULLIF(a.QTD_FATURAS, 0), 4) AS TAXA_ATRASO_90D,
    ROUND(a.VLR_FAT_CREDITO_TOTAL / NULLIF(a.VLR_FAT_BRUTO_TOTAL, 0), 4) AS TAXA_CREDITO_BRUTO,
    ROUND(a.VLR_FAT_ABERTO_TOTAL / NULLIF(a.VLR_FAT_BRUTO_TOTAL, 0), 4) AS TAXA_ABERTO_BRUTO,
    ROUND(a.VLR_MULTA_JUROS_TOTAL / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS TAXA_MULTA_JUROS,
    ROUND(a.VLR_FAT_WO / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS TAXA_VLR_WO,
    ROUND(a.VLR_FAT_PDD / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS TAXA_VLR_PDD,
    ROUND(a.VLR_FAT_BRUTO_STDDEV / NULLIF(a.VLR_FAT_BRUTO_MEDIO, 0), 4) AS COEF_VAR_FAT_BRUTO,
    ROUND(a.VLR_FAT_BRUTO_MAX / NULLIF(a.VLR_FAT_BRUTO_TOTAL, 0), 4) AS INDICE_CONCENTRACAO_FAT,
    ROUND(GREATEST(a.VLR_FAT_AUTOC, a.VLR_FAT_POSPG, a.VLR_FAT_PREPG, a.VLR_FAT_POSBL) / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS INDICE_CONCENTRACAO_PLATAFORMA,
    ROUND((a.VLR_FAT_BRUTO_MAX - a.VLR_FAT_BRUTO_MIN) / NULLIF(a.VLR_FAT_BRUTO_MEDIO, 0), 4) AS AMPLITUDE_RELATIVA_FAT,
    ROUND(a.VLR_FAT_POS_PAGO / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS SHARE_WALLET_POS_PAGO,
    ROUND(a.VLR_FAT_PRE_PAGO / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS SHARE_WALLET_PRE_PAGO,
    ROUND(a.VLR_FAT_CONTROLE / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS SHARE_WALLET_CONTROLE,
    ROUND(a.VLR_FAT_TELEMETRIA / NULLIF(a.VLR_FAT_LIQUIDO_TOTAL, 0), 4) AS SHARE_WALLET_TELEMETRIA,
    ROUND(LEAST(100, GREATEST(0,
        (COALESCE(a.QTD_FATURAS_WO / NULLIF(a.QTD_FATURAS, 0), 0) * 30) +
        (COALESCE(a.QTD_FATURAS_PDD / NULLIF(a.QTD_FATURAS, 0), 0) * 25) +
        (COALESCE(a.QTD_FATURAS_ATRASO_30D / NULLIF(a.QTD_FATURAS, 0), 0) * 20) +
        (COALESCE(a.QTD_FATURAS_FRAUDE / NULLIF(a.QTD_FATURAS, 0), 0) * 15) +
        (COALESCE(a.QTD_FATURAS_ACA / NULLIF(a.QTD_FATURAS, 0), 0) * 10)
    ) * 100), 2) AS SCORE_RISCO,
    CASE WHEN (COALESCE(a.QTD_FATURAS_WO / NULLIF(a.QTD_FATURAS, 0), 0) * 30 +
               COALESCE(a.QTD_FATURAS_PDD / NULLIF(a.QTD_FATURAS, 0), 0) * 25 +
               COALESCE(a.QTD_FATURAS_ATRASO_30D / NULLIF(a.QTD_FATURAS, 0), 0) * 20 +
               COALESCE(a.QTD_FATURAS_FRAUDE / NULLIF(a.QTD_FATURAS, 0), 0) * 15 +
               COALESCE(a.QTD_FATURAS_ACA / NULLIF(a.QTD_FATURAS, 0), 0) * 10) * 100 >= 70 THEN 1 ELSE 0 END AS FLAG_ALTO_RISCO,
    CASE WHEN (COALESCE(a.QTD_FATURAS_WO / NULLIF(a.QTD_FATURAS, 0), 0) * 30 +
               COALESCE(a.QTD_FATURAS_PDD / NULLIF(a.QTD_FATURAS, 0), 0) * 25 +
               COALESCE(a.QTD_FATURAS_ATRASO_30D / NULLIF(a.QTD_FATURAS, 0), 0) * 20 +
               COALESCE(a.QTD_FATURAS_FRAUDE / NULLIF(a.QTD_FATURAS, 0), 0) * 15 +
               COALESCE(a.QTD_FATURAS_ACA / NULLIF(a.QTD_FATURAS, 0), 0) * 10) * 100 < 30 THEN 1 ELSE 0 END AS FLAG_BAIXO_RISCO,
    CASE
        WHEN (COALESCE(a.QTD_FATURAS_WO / NULLIF(a.QTD_FATURAS, 0), 0) * 30 +
              COALESCE(a.QTD_FATURAS_PDD / NULLIF(a.QTD_FATURAS, 0), 0) * 25 +
              COALESCE(a.QTD_FATURAS_ATRASO_30D / NULLIF(a.QTD_FATURAS, 0), 0) * 20 +
              COALESCE(a.QTD_FATURAS_FRAUDE / NULLIF(a.QTD_FATURAS, 0), 0) * 15 +
              COALESCE(a.QTD_FATURAS_ACA / NULLIF(a.QTD_FATURAS, 0), 0) * 10) * 100 >= 80 THEN 'CRITICO'
        WHEN (COALESCE(a.QTD_FATURAS_WO / NULLIF(a.QTD_FATURAS, 0), 0) * 30 +
              COALESCE(a.QTD_FATURAS_PDD / NULLIF(a.QTD_FATURAS, 0), 0) * 25 +
              COALESCE(a.QTD_FATURAS_ATRASO_30D / NULLIF(a.QTD_FATURAS, 0), 0) * 20 +
              COALESCE(a.QTD_FATURAS_FRAUDE / NULLIF(a.QTD_FATURAS, 0), 0) * 15 +
              COALESCE(a.QTD_FATURAS_ACA / NULLIF(a.QTD_FATURAS, 0), 0) * 10) * 100 >= 50 THEN 'ALTO'
        WHEN (COALESCE(a.QTD_FATURAS_WO / NULLIF(a.QTD_FATURAS, 0), 0) * 30 +
              COALESCE(a.QTD_FATURAS_PDD / NULLIF(a.QTD_FATURAS, 0), 0) * 25 +
              COALESCE(a.QTD_FATURAS_ATRASO_30D / NULLIF(a.QTD_FATURAS, 0), 0) * 20 +
              COALESCE(a.QTD_FATURAS_FRAUDE / NULLIF(a.QTD_FATURAS, 0), 0) * 15 +
              COALESCE(a.QTD_FATURAS_ACA / NULLIF(a.QTD_FATURAS, 0), 0) * 10) * 100 >= 30 THEN 'MEDIO'
        ELSE 'BAIXO'
    END AS SEGMENTO_RISCO,
    current_timestamp() AS DT_PROCESSAMENTO
FROM agregado a
"""


def _safra_to_cutoff(safra):
    """Converte safra int (YYYYMM) para data cutoff string YYYY-MM-DD."""
    y, m = divmod(safra, 100)
    return date(y, m, 1).strftime("%Y-%m-%d")


def _load_views(spark):
    """Carrega tabelas Delta e registra views temporarias com broadcast."""
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "10485760")
    spark.conf.set("spark.sql.shuffle.partitions", "200")
    spark.conf.set("spark.sql.adaptive.enabled", "true")

    spark.read.format("delta").load(PATH_FATURAMENTO).createOrReplaceTempView("fato_faturamento")

    for name, path in [
        ("dim_plataforma", PATH_PLATAFORMA),
        ("dim_tipo_faturamento", PATH_TIPO_FATURAMENTO),
    ]:
        spark.read.format("delta").load(path).createOrReplaceTempView(name)

    logger.info("Views registradas (SEM dados_cadastrais — leakage fix)")


def build_book_faturamento(spark, safras=None):
    """Constroi book de variaveis de faturamento para as safras especificadas.

    NOTA: Este book NAO faz JOIN com dados_cadastrais (leakage fix Story TD-1.1).

    Args:
        spark: SparkSession ativa.
        safras: Lista de safras (int YYYYMM). Se None, usa DEFAULT_SAFRAS.

    Returns:
        dict: {safra: row_count} para cada safra processada.
    """
    if safras is None:
        safras = DEFAULT_SAFRAS

    logger.info("Book Faturamento — %d safras para processar", len(safras))
    _load_views(spark)

    results = {}
    for i, safra in enumerate(safras):
        try:
            logger.info("[%d/%d] SAFRA %d", i + 1, len(safras), safra)
            cutoff = _safra_to_cutoff(safra)

            query = SQL_TEMPLATE.format(safra=safra, data_cutoff=cutoff)
            df = spark.sql(query)
            df.cache()
            cnt = df.count()

            mode = "overwrite" if i == 0 else "append"
            df.write.format("delta") \
                .mode(mode) \
                .partitionBy("SAFRA") \
                .option("overwriteSchema", "true" if mode == "overwrite" else "false") \
                .save(PATH_OUTPUT)

            df.unpersist()
            results[safra] = cnt
            logger.info("  SAFRA %d: %d registros (modo: %s)", safra, cnt, mode)
        except Exception as e:
            logger.error("SAFRA %d falhou: %s", safra, e)
            continue

    logger.info("Book Faturamento concluido — %d registros total",
                sum(results.values()))
    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
build_book_faturamento(spark)
