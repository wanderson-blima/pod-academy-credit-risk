"""
Book de Variaveis — Pagamento.

Gera 154 variaveis comportamentais de pagamento para o modelo de credit risk,
agregadas por NUM_CPF + SAFRA. Enriquece dados transacionais de pagamento com
dimensoes (forma_pagamento, instituicao, tipo_faturamento) e calcula metricas
de volumetria, valores, pivots por status/forma/tipo, taxas e score de risco.

Inputs:
    - Silver.rawdata.pagamento (fato)
    - Silver.rawdata.forma_pagamento (dimensao)
    - Silver.rawdata.instituicao (dimensao)
    - Silver.rawdata.tipo_faturamento (dimensao)

Outputs:
    - Silver.book.pagamento (154 variaveis, particionado por SAFRA)

Uso:
    from book_pagamento import build_book_pagamento
    results = build_book_pagamento(spark, safras=[202410, 202411])
"""

from datetime import date
import logging

import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    SILVER_BASE, PATH_BOOK_PAGAMENTO, SAFRAS as DEFAULT_SAFRAS,
    SPARK_BROADCAST_THRESHOLD, SPARK_SHUFFLE_PARTITIONS, SPARK_AQE_ENABLED,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("book_pagamento")

# =============================================================================
# PATHS
# =============================================================================
_RAWDATA = f"{SILVER_BASE}/Tables/rawdata"

PATH_PAGAMENTO = f"{_RAWDATA}/pagamento"
PATH_FORMA_PAGAMENTO = f"{_RAWDATA}/forma_pagamento"
PATH_INSTITUICAO = f"{_RAWDATA}/instituicao"
PATH_TIPO_FATURAMENTO = f"{_RAWDATA}/tipo_faturamento"
PATH_OUTPUT = PATH_BOOK_PAGAMENTO

# =============================================================================
# SQL TEMPLATE (154 variaveis)
# =============================================================================
SQL_TEMPLATE = """
WITH
base_enrich AS (
    SELECT
        p.*,
        CAST('{safra}' AS INT) AS SAFRA,
        fp.DSC_FORMA_PAGAMENTO,
        i.DSC_INSTITUICAO, i.DSC_TIPO_INSTITUICAO,
        tf.DSC_TIPO_FATURAMENTO, tf.DSC_TIPO_FATURAMENTO_ABREV,
        CASE WHEN p.IND_STATUS_PAGAMENTO = 'R' THEN 1 ELSE 0 END AS FLAG_STATUS_PAGAMENTO_R,
        CASE WHEN p.IND_STATUS_PAGAMENTO = 'C' THEN 1 ELSE 0 END AS FLAG_STATUS_PAGAMENTO_C,
        CASE WHEN p.IND_STATUS_PAGAMENTO = 'P' THEN 1 ELSE 0 END AS FLAG_STATUS_PAGAMENTO_P,
        CASE WHEN p.IND_STATUS_PAGAMENTO = 'B' THEN 1 ELSE 0 END AS FLAG_STATUS_PAGAMENTO_B,
        CASE WHEN p.IND_STATUS_FATURA = 'C' THEN 1 ELSE 0 END AS FLAG_FATURA_FECHADA,
        CASE WHEN p.IND_STATUS_FATURA = 'O' THEN 1 ELSE 0 END AS FLAG_FATURA_ABERTA,
        CASE WHEN p.COD_FORMA_PAGAMENTO = 'CA' THEN 1 ELSE 0 END AS FLAG_FORMA_CA,
        CASE WHEN p.COD_FORMA_PAGAMENTO = 'PB' THEN 1 ELSE 0 END AS FLAG_FORMA_PB,
        CASE WHEN p.COD_FORMA_PAGAMENTO = 'DD' THEN 1 ELSE 0 END AS FLAG_FORMA_DD,
        CASE WHEN p.COD_FORMA_PAGAMENTO = 'PA' THEN 1 ELSE 0 END AS FLAG_FORMA_PA,
        CASE WHEN p.COD_TIPO_PAGAMENTO = 'O' THEN 1 ELSE 0 END AS FLAG_TIPO_O,
        CASE WHEN p.COD_TIPO_PAGAMENTO = 'P' THEN 1 ELSE 0 END AS FLAG_TIPO_P,
        CASE WHEN p.COD_TIPO_PAGAMENTO = 'D' THEN 1 ELSE 0 END AS FLAG_TIPO_D,
        CASE WHEN p.COD_TIPO_PAGAMENTO = 'B' THEN 1 ELSE 0 END AS FLAG_TIPO_B,
        CASE WHEN p.COD_ALOCACAO_CREDITO = 'PYM' THEN 1 ELSE 0 END AS FLAG_ALOCACAO_PYM,
        CASE WHEN p.COD_ALOCACAO_CREDITO = 'CRT' THEN 1 ELSE 0 END AS FLAG_ALOCACAO_CRT,
        CASE WHEN p.COD_ALOCACAO_CREDITO = 'CRTW' THEN 1 ELSE 0 END AS FLAG_ALOCACAO_CRTW
    FROM pagamento p
    LEFT JOIN dim_forma_pagamento fp ON p.DW_FORMA_PAGAMENTO = fp.DW_FORMA_PAGAMENTO
    LEFT JOIN dim_instituicao i ON p.DW_BANCO = i.DW_INSTITUICAO
    LEFT JOIN dim_tipo_faturamento tf ON p.DW_TIPO_FATURA = tf.DW_TIPO_FATURAMENTO
    WHERE p.DAT_STATUS_FATURA < '{data_cutoff}'
),
agregado AS (
    SELECT
        SAFRA, NUM_CPF,
        COUNT(*) AS QTD_PAGAMENTOS_TOTAL,
        COUNT(DISTINCT CONTRATO) AS QTD_CONTRATOS,
        COUNT(DISTINCT SEQ_FATURA) AS QTD_FATURAS_DISTINTAS,
        COUNT(DISTINCT DW_FORMA_PAGAMENTO) AS QTD_FORMAS_PAGAMENTO,
        COUNT(DISTINCT DW_BANCO) AS QTD_BANCOS,
        COUNT(DISTINCT DW_TIPO_FATURA) AS QTD_TIPOS_FATURA,
        COUNT(DISTINCT DW_UN_NEGOCIO) AS QTD_UN_NEGOCIOS,
        COUNT(DISTINCT DW_AREA) AS QTD_AREAS,
        SUM(COALESCE(VAL_PAGAMENTO_FATURA, 0)) AS VLR_PAGAMENTO_FATURA_TOTAL,
        AVG(COALESCE(VAL_PAGAMENTO_FATURA, 0)) AS VLR_PAGAMENTO_FATURA_MEDIO,
        MAX(COALESCE(VAL_PAGAMENTO_FATURA, 0)) AS VLR_PAGAMENTO_FATURA_MAX,
        STDDEV(COALESCE(VAL_PAGAMENTO_FATURA, 0)) AS VLR_PAGAMENTO_FATURA_STDDEV,
        SUM(COALESCE(VAL_PAGAMENTO_ITEM, 0)) AS VLR_PAGAMENTO_ITEM_TOTAL,
        AVG(COALESCE(VAL_PAGAMENTO_ITEM, 0)) AS VLR_PAGAMENTO_ITEM_MEDIO,
        SUM(COALESCE(VAL_PAGAMENTO_CREDITO, 0)) AS VLR_PAGAMENTO_CREDITO_TOTAL,
        AVG(COALESCE(VAL_PAGAMENTO_CREDITO, 0)) AS VLR_PAGAMENTO_CREDITO_MEDIO,
        MAX(COALESCE(VAL_PAGAMENTO_CREDITO, 0)) AS VLR_PAGAMENTO_CREDITO_MAX,
        SUM(COALESCE(VAL_ATUAL_PAGAMENTO, 0)) AS VLR_ATUAL_PAGAMENTO_TOTAL,
        AVG(COALESCE(VAL_ATUAL_PAGAMENTO, 0)) AS VLR_ATUAL_PAGAMENTO_MEDIO,
        SUM(COALESCE(VAL_ORIGINAL_PAGAMENTO, 0)) AS VLR_ORIGINAL_PAGAMENTO_TOTAL,
        AVG(COALESCE(VAL_ORIGINAL_PAGAMENTO, 0)) AS VLR_ORIGINAL_PAGAMENTO_MEDIO,
        SUM(COALESCE(VAL_BAIXA_ATIVIDADE, 0)) AS VLR_BAIXA_ATIVIDADE_TOTAL,
        AVG(COALESCE(VAL_BAIXA_ATIVIDADE, 0)) AS VLR_BAIXA_ATIVIDADE_MEDIO,
        SUM(COALESCE(VAL_JUROS_MULTAS_ITEM, 0)) AS VLR_JUROS_MULTAS_TOTAL,
        AVG(COALESCE(VAL_JUROS_MULTAS_ITEM, 0)) AS VLR_JUROS_MULTAS_MEDIO,
        MAX(COALESCE(VAL_JUROS_MULTAS_ITEM, 0)) AS VLR_JUROS_MULTAS_MAX,
        COUNT(CASE WHEN VAL_JUROS_MULTAS_ITEM > 0 THEN 1 END) AS QTD_PAGAMENTOS_COM_JUROS,
        SUM(COALESCE(VAL_MULTA_EQUIP_ITEM, 0)) AS VLR_MULTA_EQUIP_TOTAL,
        COUNT(CASE WHEN VAL_MULTA_EQUIP_ITEM > 0 THEN 1 END) AS QTD_MULTAS_EQUIP,
        SUM(FLAG_STATUS_PAGAMENTO_R) AS QTD_STATUS_R,
        SUM(FLAG_STATUS_PAGAMENTO_C) AS QTD_STATUS_C,
        SUM(FLAG_STATUS_PAGAMENTO_P) AS QTD_STATUS_P,
        SUM(FLAG_STATUS_PAGAMENTO_B) AS QTD_STATUS_B,
        SUM(CASE WHEN FLAG_STATUS_PAGAMENTO_R = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_STATUS_R,
        SUM(CASE WHEN FLAG_STATUS_PAGAMENTO_C = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_STATUS_C,
        SUM(CASE WHEN FLAG_STATUS_PAGAMENTO_P = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_STATUS_P,
        SUM(CASE WHEN FLAG_STATUS_PAGAMENTO_B = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_STATUS_B,
        SUM(FLAG_FATURA_FECHADA) AS QTD_FATURA_FECHADA,
        SUM(FLAG_FATURA_ABERTA) AS QTD_FATURA_ABERTA,
        SUM(CASE WHEN FLAG_FATURA_FECHADA = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_FATURA_FECHADA,
        SUM(CASE WHEN FLAG_FATURA_ABERTA = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_FATURA_ABERTA,
        SUM(FLAG_FORMA_CA) AS QTD_FORMA_CA,
        SUM(FLAG_FORMA_PB) AS QTD_FORMA_PB,
        SUM(FLAG_FORMA_DD) AS QTD_FORMA_DD,
        SUM(FLAG_FORMA_PA) AS QTD_FORMA_PA,
        SUM(CASE WHEN FLAG_FORMA_CA = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_FORMA_CA,
        SUM(CASE WHEN FLAG_FORMA_PB = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_FORMA_PB,
        SUM(CASE WHEN FLAG_FORMA_DD = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_FORMA_DD,
        SUM(CASE WHEN FLAG_FORMA_PA = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_FORMA_PA,
        SUM(FLAG_TIPO_O) AS QTD_TIPO_O,
        SUM(FLAG_TIPO_P) AS QTD_TIPO_P,
        SUM(FLAG_TIPO_D) AS QTD_TIPO_D,
        SUM(FLAG_TIPO_B) AS QTD_TIPO_B,
        SUM(CASE WHEN FLAG_TIPO_O = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_TIPO_O,
        SUM(CASE WHEN FLAG_TIPO_P = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_TIPO_P,
        SUM(CASE WHEN FLAG_TIPO_D = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_TIPO_D,
        SUM(CASE WHEN FLAG_TIPO_B = 1 THEN COALESCE(VAL_PAGAMENTO_FATURA, 0) ELSE 0 END) AS VLR_TIPO_B,
        SUM(FLAG_ALOCACAO_PYM) AS QTD_ALOCACAO_PYM,
        SUM(FLAG_ALOCACAO_CRT) AS QTD_ALOCACAO_CRT,
        SUM(FLAG_ALOCACAO_CRTW) AS QTD_ALOCACAO_CRTW,
        SUM(CASE WHEN FLAG_ALOCACAO_PYM = 1 THEN COALESCE(VAL_PAGAMENTO_CREDITO, 0) ELSE 0 END) AS VLR_ALOCACAO_PYM,
        SUM(CASE WHEN FLAG_ALOCACAO_CRT = 1 THEN COALESCE(VAL_PAGAMENTO_CREDITO, 0) ELSE 0 END) AS VLR_ALOCACAO_CRT,
        MIN(DAT_STATUS_FATURA) AS DT_PRIMEIRA_FATURA,
        MAX(DAT_STATUS_FATURA) AS DT_ULTIMA_FATURA,
        MIN(DAT_CRIACAO_DW) AS DT_PRIMEIRA_CRIACAO_DW,
        MAX(DAT_CRIACAO_DW) AS DT_ULTIMA_CRIACAO_DW,
        DATEDIFF(MAX(DAT_STATUS_FATURA), MIN(DAT_STATUS_FATURA)) AS DIAS_ENTRE_FATURAS,
        DATEDIFF(TO_DATE('{data_cutoff}'), MAX(DAT_STATUS_FATURA)) AS DIAS_DESDE_ULTIMA_FATURA,
        AVG(DATEDIFF(DAT_BAIXA_ATIVIDADE, DAT_CRIACAO_ATIVIDADE)) AS DIAS_MEDIO_BAIXA,
        AVG(DATEDIFF(DAT_DEPOSITO_ATIVIDADE, DAT_CRIACAO_ATIVIDADE)) AS DIAS_MEDIO_DEPOSITO,
        COUNT(DISTINCT DATE_FORMAT(DAT_STATUS_FATURA, 'yyyyMM')) AS QTD_MESES_ATIVOS,
        -- NOTA: FIRST() sem ORDER BY e nao-deterministico, aceitavel (colunas descritivas nao usadas na modelagem)
        FIRST(DSC_FORMA_PAGAMENTO) AS FORMA_PAGAMENTO_PRINCIPAL,
        FIRST(DSC_TIPO_INSTITUICAO) AS TIPO_INSTITUICAO_PRINCIPAL,
        FIRST(DSC_TIPO_FATURAMENTO_ABREV) AS TIPO_FATURAMENTO_PRINCIPAL,
        COUNT(DISTINCT DSC_TIPO_INSTITUICAO) AS QTD_TIPOS_INSTITUICAO
    FROM base_enrich
    GROUP BY SAFRA, NUM_CPF
)
SELECT
    a.*,
    a.QTD_STATUS_R / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_STATUS_R,
    a.QTD_STATUS_C / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_STATUS_C,
    a.QTD_STATUS_P / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_STATUS_P,
    a.QTD_STATUS_B / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_STATUS_B,
    a.QTD_FORMA_CA / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_FORMA_CA,
    a.QTD_FORMA_PB / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_FORMA_PB,
    a.QTD_FORMA_DD / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_FORMA_DD,
    a.QTD_FORMA_PA / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_FORMA_PA,
    a.QTD_FATURA_ABERTA / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_FATURA_ABERTA,
    a.QTD_PAGAMENTOS_COM_JUROS / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0) AS TAXA_PAGAMENTOS_COM_JUROS,
    a.VLR_JUROS_MULTAS_TOTAL / NULLIF(a.VLR_PAGAMENTO_FATURA_TOTAL, 0) AS TAXA_JUROS_SOBRE_PAGAMENTO,
    a.VLR_PAGAMENTO_FATURA_STDDEV / NULLIF(a.VLR_PAGAMENTO_FATURA_MEDIO, 0) AS COEF_VARIACAO_PAGAMENTO,
    a.VLR_PAGAMENTO_FATURA_MAX / NULLIF(a.VLR_PAGAMENTO_FATURA_TOTAL, 0) AS INDICE_CONCENTRACAO,
    a.VLR_PAGAMENTO_FATURA_TOTAL / NULLIF(a.QTD_CONTRATOS, 0) AS VLR_TICKET_MEDIO_CONTRATO,
    a.VLR_ORIGINAL_PAGAMENTO_TOTAL - a.VLR_ATUAL_PAGAMENTO_TOTAL AS VLR_DIFERENCA_ORIG_ATUAL,
    LEAST(100, GREATEST(0,
        COALESCE(a.QTD_FATURA_ABERTA / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0), 0) * 25 +
        LEAST(1, COALESCE(a.VLR_JUROS_MULTAS_TOTAL / NULLIF(a.VLR_PAGAMENTO_FATURA_TOTAL, 0), 0) * 5) * 25 +
        COALESCE(a.QTD_STATUS_B / NULLIF(CAST(a.QTD_PAGAMENTOS_TOTAL AS DOUBLE), 0), 0) * 20 +
        LEAST(1, COALESCE(a.VLR_PAGAMENTO_FATURA_STDDEV / NULLIF(a.VLR_PAGAMENTO_FATURA_MEDIO, 0), 0)) * 15 +
        CASE WHEN a.QTD_MULTAS_EQUIP > 0 THEN 15 ELSE 0 END
    )) AS SCORE_RISCO,
    CASE
        WHEN a.QTD_FATURA_ABERTA > a.QTD_FATURA_FECHADA THEN 1
        WHEN a.VLR_JUROS_MULTAS_TOTAL > a.VLR_PAGAMENTO_FATURA_TOTAL * 0.1 THEN 1
        WHEN a.QTD_STATUS_B > a.QTD_PAGAMENTOS_TOTAL * 0.3 THEN 1
        ELSE 0
    END AS FLAG_ALTO_RISCO,
    CASE
        WHEN a.QTD_FATURA_ABERTA = 0
            AND a.VLR_JUROS_MULTAS_TOTAL = 0
            AND a.QTD_STATUS_C > a.QTD_PAGAMENTOS_TOTAL * 0.9 THEN 1
        ELSE 0
    END AS FLAG_BAIXO_RISCO,
    CASE
        WHEN a.QTD_FATURA_ABERTA > a.QTD_FATURA_FECHADA
            OR a.VLR_JUROS_MULTAS_TOTAL > a.VLR_PAGAMENTO_FATURA_TOTAL * 0.2 THEN 'CRITICO'
        WHEN a.QTD_FATURA_ABERTA > 0
            OR a.VLR_JUROS_MULTAS_TOTAL > a.VLR_PAGAMENTO_FATURA_TOTAL * 0.1 THEN 'ALTO'
        WHEN a.VLR_JUROS_MULTAS_TOTAL > 0
            OR a.QTD_STATUS_P > a.QTD_PAGAMENTOS_TOTAL * 0.1 THEN 'MEDIO'
        ELSE 'BAIXO'
    END AS SEGMENTO_RISCO,
    CURRENT_TIMESTAMP() AS DT_PROCESSAMENTO
FROM agregado a
"""


def _safra_to_cutoff(safra):
    """Converte safra int (YYYYMM) para data cutoff string YYYY-MM-DD."""
    y, m = divmod(safra, 100)
    return date(y, m, 1).strftime("%Y-%m-%d")


def _load_views(spark):
    """Carrega tabelas Delta e registra views temporarias com broadcast."""
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(SPARK_BROADCAST_THRESHOLD))
    spark.conf.set("spark.sql.adaptive.enabled", str(SPARK_AQE_ENABLED).lower())
    spark.conf.set("spark.sql.shuffle.partitions", str(SPARK_SHUFFLE_PARTITIONS))

    spark.read.format("delta").load(PATH_PAGAMENTO).createOrReplaceTempView("pagamento")

    for name, path in [
        ("dim_forma_pagamento", PATH_FORMA_PAGAMENTO),
        ("dim_instituicao", PATH_INSTITUICAO),
        ("dim_tipo_faturamento", PATH_TIPO_FATURAMENTO),
    ]:
        spark.read.format("delta").load(path).createOrReplaceTempView(name)

    logger.info("Views registradas (broadcast threshold: 10MB)")


def build_book_pagamento(spark, safras=None):
    """Constroi book de variaveis de pagamento para as safras especificadas.

    Args:
        spark: SparkSession ativa.
        safras: Lista de safras (int YYYYMM). Se None, usa DEFAULT_SAFRAS.

    Returns:
        dict: {safra: row_count} para cada safra processada.
    """
    if safras is None:
        safras = DEFAULT_SAFRAS

    logger.info("Book Pagamento — %d safras para processar", len(safras))
    _load_views(spark)

    results = {}
    failed = []
    first_success = True
    for i, safra in enumerate(safras):
        # Validar SAFRA
        y, m = divmod(safra, 100)
        if not (1 <= m <= 12):
            raise ValueError(f"SAFRA invalida {safra}: mes {m} fora de 1-12")
        try:
            logger.info("[%d/%d] SAFRA %d", i + 1, len(safras), safra)
            cutoff = _safra_to_cutoff(safra)

            query = SQL_TEMPLATE.format(safra=safra, data_cutoff=cutoff)
            df = spark.sql(query)

            df.write.format("delta") \
                .mode("overwrite") \
                .option("replaceWhere", f"SAFRA = {safra}") \
                .partitionBy("SAFRA") \
                .option("overwriteSchema", "true" if first_success else "false") \
                .save(PATH_OUTPUT)

            first_success = False
            logger.info("  SAFRA %d escrita com sucesso", safra)
        except Exception as e:
            logger.error("SAFRA %d falhou: %s", safra, e, exc_info=True)
            failed.append(safra)
            continue

    if failed:
        logger.warning("SAFRAs com falha: %s", failed)

    # Contagem final via Delta (evita cache/count no loop)
    df_final = spark.read.format("delta").load(PATH_OUTPUT)
    for safra in safras:
        cnt = df_final.filter(f"SAFRA = {safra}").count()
        results[safra] = cnt
        if cnt == 0 and safra not in failed:
            logger.warning("  SAFRA %d: 0 registros (possivel problema no filtro)", safra)
        else:
            logger.info("  SAFRA %d: %d registros", safra, cnt)

    logger.info("Book Pagamento concluido — %d registros total",
                sum(results.values()))
    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
build_book_pagamento(spark)
