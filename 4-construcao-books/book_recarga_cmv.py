"""
Book de Variaveis — Recarga CMV.

Gera 102 variaveis comportamentais de recarga para o modelo de credit risk,
agregadas por NUM_CPF + SAFRA. Enriquece dados transacionais de recarga com
dimensoes (canal, plano, tipo_recarga, tipo_insercao, forma_pagamento,
instituicao) e calcula metricas de volumetria, valores, pivots, taxas,
indices de estabilidade e score de risco.

Inputs:
    - Silver.rawdata.ass_recarga_cmv_nova (fato)
    - Silver.rawdata.canal_aquisicao_credito (dimensao)
    - Silver.rawdata.plano_preco (dimensao)
    - Silver.rawdata.tipo_recarga (dimensao)
    - Silver.rawdata.tipo_insercao (dimensao)
    - Silver.rawdata.forma_pagamento (dimensao)
    - Silver.rawdata.instituicao (dimensao)

Outputs:
    - Silver.book.ass_recarga_cmv (102 variaveis, particionado por SAFRA)

Uso:
    from book_recarga_cmv import build_book_recarga
    results = build_book_recarga(spark, safras=[202410, 202411])
"""

from datetime import date
import logging

import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    SILVER_BASE, PATH_BOOK_RECARGA_CMV, SAFRAS as DEFAULT_SAFRAS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("book_recarga")

# =============================================================================
# PATHS
# =============================================================================
_RAWDATA = f"{SILVER_BASE}/Tables/rawdata"

PATH_RECARGA = f"{_RAWDATA}/ass_recarga_cmv_nova"
PATH_CANAL = f"{_RAWDATA}/canal_aquisicao_credito"
PATH_PLANO = f"{_RAWDATA}/plano_preco"
PATH_TIPO_RECARGA = f"{_RAWDATA}/tipo_recarga"
PATH_TIPO_INSERCAO = f"{_RAWDATA}/tipo_insercao"
PATH_FORMA_PAGAMENTO = f"{_RAWDATA}/forma_pagamento"
PATH_INSTITUICAO = f"{_RAWDATA}/instituicao"
PATH_OUTPUT = PATH_BOOK_RECARGA_CMV

# =============================================================================
# SQL TEMPLATE (102 variaveis)
# =============================================================================
SQL_TEMPLATE = """
WITH
base_enrich AS (
    SELECT
        r.*,
        CAST('{safra}' AS INT) AS SAFRA,
        c.DSC_CANAL_AQUISICAO_BI,
        c.COD_TIPO_CREDITO AS CANAL_TIPO_CREDITO,
        p.DSC_TIPO_PLANO_BI,
        p.DSC_GRUPO_PLANO_BI,
        p.IND_AMDOCS_PLAT_PRE,
        tr.DSC_TIPO_RECARGA,
        ti.DSC_TIPO_INSERCAO,
        fp.DSC_FORMA_PAGAMENTO,
        i.DSC_INSTITUICAO,
        i.DSC_TIPO_INSTITUICAO,
        CASE WHEN r.COD_PLATAFORMA_ATU = 'PREPG' THEN 1 ELSE 0 END AS FLAG_PLAT_PREPG,
        CASE WHEN r.COD_PLATAFORMA_ATU = 'AUTOC' THEN 1 ELSE 0 END AS FLAG_PLAT_AUTOC,
        CASE WHEN r.COD_PLATAFORMA_ATU = 'FLEXD' THEN 1 ELSE 0 END AS FLAG_PLAT_FLEXD,
        CASE WHEN r.COD_PLATAFORMA_ATU = 'CTLFC' THEN 1 ELSE 0 END AS FLAG_PLAT_CTLFC,
        CASE WHEN r.COD_PLATAFORMA_ATU = 'POSPG' THEN 1 ELSE 0 END AS FLAG_PLAT_POSPG,
        CASE WHEN r.COD_STATUS_PLATAFORMA = 'A' THEN 1 ELSE 0 END AS FLAG_STATUS_A,
        CASE WHEN r.COD_STATUS_PLATAFORMA = 'ZB1' THEN 1 ELSE 0 END AS FLAG_STATUS_ZB1,
        CASE WHEN r.COD_STATUS_PLATAFORMA = 'ZB2' THEN 1 ELSE 0 END AS FLAG_STATUS_ZB2,
        CASE WHEN r.COD_STATUS_PLATAFORMA = 'NDF' THEN 1 ELSE 0 END AS FLAG_STATUS_NDF,
        CASE WHEN r.DSC_GRUPO_CARTAO_WPP = 'NaoSeAplica' THEN 1 ELSE 0 END AS FLAG_CARTAO_NA,
        CASE WHEN r.DSC_GRUPO_CARTAO_WPP = 'Rec.Online' THEN 1 ELSE 0 END AS FLAG_CARTAO_ONLINE,
        CASE WHEN r.DSC_GRUPO_CARTAO_WPP = 'AtivPromocao' THEN 1 ELSE 0 END AS FLAG_CARTAO_PROMO,
        CASE WHEN r.DSC_GRUPO_CARTAO_WPP LIKE 'ChipPre%' THEN 1 ELSE 0 END AS FLAG_CARTAO_CHIPPRE,
        CASE WHEN p.DSC_TIPO_PLANO_BI = 'Varejo' THEN 1 ELSE 0 END AS FLAG_PLANO_VAREJO,
        CASE WHEN p.DSC_TIPO_PLANO_BI = 'Corporativos' THEN 1 ELSE 0 END AS FLAG_PLANO_CORP,
        CASE WHEN p.DSC_TIPO_PLANO_BI = 'Mid' THEN 1 ELSE 0 END AS FLAG_PLANO_MID,
        CASE WHEN i.DSC_TIPO_INSTITUICAO = 'Distribuidor Regional' THEN 1 ELSE 0 END AS FLAG_INST_DIST_REG,
        CASE WHEN i.DSC_TIPO_INSTITUICAO = 'Street Seller' THEN 1 ELSE 0 END AS FLAG_INST_STREET,
        CASE WHEN i.DSC_TIPO_INSTITUICAO = 'Venda Direta' THEN 1 ELSE 0 END AS FLAG_INST_DIRETA,
        CASE WHEN i.DSC_TIPO_INSTITUICAO = 'Varejo' THEN 1 ELSE 0 END AS FLAG_INST_VAREJO,
        COALESCE(r.FLAG_SOS, 0) AS FLAG_SOS_CLEAN,
        CASE WHEN r.COD_PLATAFORMA_ATU IN ('CTLFC', 'FLEXD') THEN 1 ELSE 0 END AS FLAG_PLAT_CONTROLE
    FROM recarga r
    LEFT JOIN dim_canal c ON r.COD_CANAL_AQUISICAO = c.COD_CANAL_AQUISICAO
    LEFT JOIN dim_plano p ON r.DW_PLANO_TARIFACAO = p.DW_PLANO
    LEFT JOIN dim_tipo_recarga tr ON r.DW_TIPO_RECARGA = tr.DW_TIPO_RECARGA
    LEFT JOIN dim_tipo_insercao ti ON r.DW_TIPO_INSERCAO = ti.DW_TIPO_INSERCAO
    LEFT JOIN dim_forma_pagamento fp ON r.DW_FORMA_PAGAMENTO = fp.DW_FORMA_PAGAMENTO
    LEFT JOIN dim_instituicao i ON r.DW_INSTITUICAO = i.DW_INSTITUICAO
    WHERE r.DAT_INSERCAO_CREDITO < '{data_cutoff}'
),
agregado AS (
    SELECT
        SAFRA, NUM_CPF,
        COUNT(*) AS QTD_RECARGAS_TOTAL,
        COUNT(DISTINCT DW_NUM_NTC) AS QTD_LINHAS,
        COUNT(DISTINCT DW_NUM_CLIENTE) AS QTD_CLIENTES_DW,
        COUNT(DISTINCT COD_PLATAFORMA_ATU) AS QTD_PLATAFORMAS,
        COUNT(DISTINCT DW_TIPO_RECARGA) AS QTD_TIPOS_RECARGA,
        COUNT(DISTINCT DW_TIPO_INSERCAO) AS QTD_TIPOS_INSERCAO,
        COUNT(DISTINCT DW_FORMA_PAGAMENTO) AS QTD_FORMAS_PAGTO,
        COUNT(DISTINCT DW_INSTITUICAO) AS QTD_INSTITUICOES,
        COUNT(DISTINCT DW_PLANO_TARIFACAO) AS QTD_PLANOS,
        COUNT(DISTINCT DATE(DAT_INSERCAO_CREDITO)) AS QTD_DIAS_RECARGA,
        SUM(COALESCE(VAL_CREDITO_INSERIDO, 0)) AS VLR_CREDITO_TOTAL,
        AVG(COALESCE(VAL_CREDITO_INSERIDO, 0)) AS VLR_CREDITO_MEDIO,
        MAX(COALESCE(VAL_CREDITO_INSERIDO, 0)) AS VLR_CREDITO_MAX,
        MIN(CASE WHEN VAL_CREDITO_INSERIDO > 0 THEN VAL_CREDITO_INSERIDO END) AS VLR_CREDITO_MIN,
        STDDEV(COALESCE(VAL_CREDITO_INSERIDO, 0)) AS VLR_CREDITO_STDDEV,
        SUM(COALESCE(VAL_BONUS, 0)) AS VLR_BONUS_TOTAL,
        AVG(COALESCE(VAL_BONUS, 0)) AS VLR_BONUS_MEDIO,
        MAX(COALESCE(VAL_BONUS, 0)) AS VLR_BONUS_MAX,
        SUM(COALESCE(VAL_REAL, 0)) AS VLR_REAL_TOTAL,
        AVG(COALESCE(VAL_REAL, 0)) AS VLR_REAL_MEDIO,
        MAX(COALESCE(VAL_REAL, 0)) AS VLR_REAL_MAX,
        STDDEV(COALESCE(VAL_REAL, 0)) AS VLR_REAL_STDDEV,
        SUM(FLAG_PLAT_PREPG) AS QTD_PLAT_PREPG,
        SUM(FLAG_PLAT_AUTOC) AS QTD_PLAT_AUTOC,
        SUM(FLAG_PLAT_FLEXD) AS QTD_PLAT_FLEXD,
        SUM(FLAG_PLAT_CTLFC) AS QTD_PLAT_CTLFC,
        SUM(FLAG_PLAT_POSPG) AS QTD_PLAT_POSPG,
        SUM(CASE WHEN FLAG_PLAT_PREPG = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_PLAT_PREPG,
        SUM(CASE WHEN FLAG_PLAT_AUTOC = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_PLAT_AUTOC,
        SUM(CASE WHEN FLAG_PLAT_FLEXD = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_PLAT_FLEXD,
        SUM(CASE WHEN FLAG_PLAT_CTLFC = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_PLAT_CTLFC,
        SUM(FLAG_PLAT_CONTROLE) AS QTD_PLAT_CONTROLE,
        SUM(FLAG_STATUS_A) AS QTD_STATUS_A,
        SUM(FLAG_STATUS_ZB1) AS QTD_STATUS_ZB1,
        SUM(FLAG_STATUS_ZB2) AS QTD_STATUS_ZB2,
        SUM(FLAG_STATUS_NDF) AS QTD_STATUS_NDF,
        SUM(CASE WHEN FLAG_STATUS_A = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_STATUS_A,
        SUM(CASE WHEN FLAG_STATUS_ZB1 = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_STATUS_ZB1,
        SUM(CASE WHEN FLAG_STATUS_ZB2 = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_STATUS_ZB2,
        SUM(FLAG_CARTAO_NA) AS QTD_CARTAO_NA,
        SUM(FLAG_CARTAO_ONLINE) AS QTD_CARTAO_ONLINE,
        SUM(FLAG_CARTAO_PROMO) AS QTD_CARTAO_PROMO,
        SUM(FLAG_CARTAO_CHIPPRE) AS QTD_CARTAO_CHIPPRE,
        SUM(CASE WHEN FLAG_CARTAO_ONLINE = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_CARTAO_ONLINE,
        SUM(CASE WHEN FLAG_CARTAO_PROMO = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_CARTAO_PROMO,
        SUM(FLAG_PLANO_VAREJO) AS QTD_PLANO_VAREJO,
        SUM(FLAG_PLANO_CORP) AS QTD_PLANO_CORP,
        SUM(FLAG_PLANO_MID) AS QTD_PLANO_MID,
        SUM(CASE WHEN FLAG_PLANO_VAREJO = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_PLANO_VAREJO,
        SUM(CASE WHEN FLAG_PLANO_CORP = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_PLANO_CORP,
        SUM(FLAG_INST_DIST_REG) AS QTD_INST_DIST_REG,
        SUM(FLAG_INST_STREET) AS QTD_INST_STREET,
        SUM(FLAG_INST_DIRETA) AS QTD_INST_DIRETA,
        SUM(FLAG_INST_VAREJO) AS QTD_INST_VAREJO,
        SUM(CASE WHEN FLAG_INST_STREET = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_INST_STREET,
        SUM(CASE WHEN FLAG_INST_DIRETA = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_INST_DIRETA,
        SUM(FLAG_SOS_CLEAN) AS QTD_SOS,
        SUM(CASE WHEN FLAG_SOS_CLEAN = 1 THEN COALESCE(VAL_CREDITO_INSERIDO, 0) ELSE 0 END) AS VLR_SOS_TOTAL,
        MIN(DAT_INSERCAO_CREDITO) AS DT_PRIMEIRA_RECARGA,
        MAX(DAT_INSERCAO_CREDITO) AS DT_ULTIMA_RECARGA,
        DATEDIFF(MAX(DAT_INSERCAO_CREDITO), MIN(DAT_INSERCAO_CREDITO)) AS DIAS_ENTRE_RECARGAS,
        DATEDIFF(TO_DATE('{data_cutoff}'), MAX(DAT_INSERCAO_CREDITO)) AS DIAS_DESDE_ULTIMA_RECARGA,
        DATEDIFF(TO_DATE('{data_cutoff}'), MIN(DAT_INSERCAO_CREDITO)) AS DIAS_DESDE_PRIMEIRA_RECARGA,
        COUNT(DISTINCT DATE_FORMAT(DAT_INSERCAO_CREDITO, 'yyyyMM')) AS QTD_MESES_ATIVOS,
        FIRST(DSC_TIPO_PLANO_BI) AS TIPO_PLANO_PRINCIPAL,
        FIRST(DSC_TIPO_INSTITUICAO) AS TIPO_INSTITUICAO_PRINCIPAL,
        FIRST(DSC_GRUPO_CARTAO_WPP) AS GRUPO_CARTAO_PRINCIPAL,
        FIRST(COD_PLATAFORMA_ATU) AS PLATAFORMA_PRINCIPAL
    FROM base_enrich
    GROUP BY SAFRA, NUM_CPF
)
SELECT
    a.*,
    a.QTD_PLAT_PREPG / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_PLAT_PREPG,
    a.QTD_PLAT_AUTOC / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_PLAT_AUTOC,
    a.QTD_PLAT_CONTROLE / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_PLAT_CONTROLE,
    a.QTD_STATUS_A / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_STATUS_A,
    a.QTD_STATUS_ZB1 / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_STATUS_ZB1,
    a.QTD_STATUS_ZB2 / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_STATUS_ZB2,
    a.QTD_CARTAO_ONLINE / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_CARTAO_ONLINE,
    a.QTD_CARTAO_PROMO / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_CARTAO_PROMO,
    a.QTD_SOS / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0) AS TAXA_SOS,
    a.VLR_PLAT_PREPG / NULLIF(a.VLR_CREDITO_TOTAL, 0) AS SHARE_PLAT_PREPG,
    a.VLR_PLAT_AUTOC / NULLIF(a.VLR_CREDITO_TOTAL, 0) AS SHARE_PLAT_AUTOC,
    a.VLR_CARTAO_ONLINE / NULLIF(a.VLR_CREDITO_TOTAL, 0) AS SHARE_CARTAO_ONLINE,
    a.VLR_CREDITO_STDDEV / NULLIF(a.VLR_CREDITO_MEDIO, 0) AS COEF_VARIACAO_CREDITO,
    a.VLR_REAL_STDDEV / NULLIF(a.VLR_REAL_MEDIO, 0) AS COEF_VARIACAO_REAL,
    a.VLR_CREDITO_MAX / NULLIF(a.VLR_CREDITO_TOTAL, 0) AS INDICE_CONCENTRACAO_CREDITO,
    a.VLR_CREDITO_TOTAL / NULLIF(a.QTD_LINHAS, 0) AS VLR_TICKET_MEDIO_LINHA,
    a.QTD_RECARGAS_TOTAL / NULLIF(GREATEST(a.DIAS_ENTRE_RECARGAS, 1), 0) AS FREQ_RECARGA_DIARIA,
    a.VLR_BONUS_TOTAL / NULLIF(a.VLR_CREDITO_TOTAL, 0) AS RATIO_BONUS_CREDITO,
    LEAST(100, GREATEST(0,
        COALESCE(a.QTD_PLAT_CONTROLE / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0), 0) * 30 +
        COALESCE((a.QTD_STATUS_ZB1 + a.QTD_STATUS_ZB2) / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0), 0) * 25 +
        LEAST(1, COALESCE(a.QTD_SOS / NULLIF(CAST(a.QTD_RECARGAS_TOTAL AS DOUBLE), 0), 0) * 3) * 20 +
        LEAST(1, COALESCE(a.VLR_CREDITO_STDDEV / NULLIF(a.VLR_CREDITO_MEDIO, 0), 0)) * 15 +
        LEAST(1, COALESCE(a.VLR_CREDITO_MAX / NULLIF(a.VLR_CREDITO_TOTAL, 0), 0)) * 10
    )) AS SCORE_RISCO,
    CASE
        WHEN a.QTD_PLAT_CONTROLE > a.QTD_RECARGAS_TOTAL * 0.5 THEN 1
        WHEN (a.QTD_STATUS_ZB1 + a.QTD_STATUS_ZB2) > a.QTD_RECARGAS_TOTAL * 0.3 THEN 1
        WHEN a.QTD_SOS > a.QTD_RECARGAS_TOTAL * 0.2 THEN 1
        ELSE 0
    END AS FLAG_ALTO_RISCO,
    CASE
        WHEN a.QTD_PLAT_PREPG = a.QTD_RECARGAS_TOTAL
            AND a.QTD_STATUS_A > a.QTD_RECARGAS_TOTAL * 0.95
            AND a.QTD_SOS = 0 THEN 1
        ELSE 0
    END AS FLAG_BAIXO_RISCO,
    CASE
        WHEN a.QTD_PLAT_CONTROLE > a.QTD_RECARGAS_TOTAL * 0.5
            OR (a.QTD_STATUS_ZB1 + a.QTD_STATUS_ZB2) > a.QTD_RECARGAS_TOTAL * 0.3 THEN 'CRITICO'
        WHEN a.QTD_PLAT_CONTROLE > 0
            OR a.QTD_SOS > a.QTD_RECARGAS_TOTAL * 0.1 THEN 'ALTO'
        WHEN a.QTD_STATUS_ZB1 > 0 OR a.QTD_SOS > 0 THEN 'MEDIO'
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
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "10485760")

    spark.read.format("delta").load(PATH_RECARGA).createOrReplaceTempView("recarga")

    for name, path in [
        ("dim_canal", PATH_CANAL),
        ("dim_plano", PATH_PLANO),
        ("dim_tipo_recarga", PATH_TIPO_RECARGA),
        ("dim_tipo_insercao", PATH_TIPO_INSERCAO),
        ("dim_forma_pagamento", PATH_FORMA_PAGAMENTO),
        ("dim_instituicao", PATH_INSTITUICAO),
    ]:
        spark.read.format("delta").load(path).createOrReplaceTempView(name)

    logger.info("Views registradas (broadcast threshold: 10MB)")


def build_book_recarga(spark, safras=None):
    """Constroi book de variaveis de recarga para as safras especificadas.

    Args:
        spark: SparkSession ativa.
        safras: Lista de safras (int YYYYMM). Se None, usa DEFAULT_SAFRAS.

    Returns:
        dict: {safra: row_count} para cada safra processada.
    """
    if safras is None:
        safras = DEFAULT_SAFRAS

    logger.info("Book Recarga — %d safras para processar", len(safras))
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

    logger.info("Book Recarga concluido — %d registros total",
                sum(results.values()))
    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
build_book_recarga(spark)
