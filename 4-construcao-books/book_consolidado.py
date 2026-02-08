"""
Book Consolidado — Feature Store (Gold).

Consolida todas as fontes de dados (cadastro, telco, score_bureau, books de
recarga/pagamento/faturamento) em um unico dataset enriquecido para modelos ML.
Resultado: ~468 variaveis no Gold.feature_store.clientes_consolidado.

Inputs:
    - Silver.rawdata.dados_cadastrais (base, 33 cols)
    - Silver.rawdata.telco (68 cols)
    - Silver.rawdata.score_bureau_movel_full (2 cols TARGET)
    - Silver.book.ass_recarga_cmv (102 cols, prefixo REC_)
    - Silver.book.pagamento (154 cols, prefixo PAG_)
    - Silver.book.faturamento (108 cols, prefixo FAT_)

Outputs:
    - Gold.feature_store.clientes_consolidado (~468 variaveis, particionado por SAFRA)

Uso:
    from book_consolidado import build_book_consolidado
    results = build_book_consolidado(spark)
"""

import logging

import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    PATH_DADOS_CADASTRAIS, PATH_TELCO, PATH_SCORE_BUREAU,
    PATH_BOOK_RECARGA_CMV, PATH_BOOK_PAGAMENTO, PATH_BOOK_FATURAMENTO,
    PATH_FEATURE_STORE, SAFRAS as DEFAULT_SAFRAS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("book_consolidado")

# =============================================================================
# COLUNAS A EXCLUIR
# =============================================================================
_METADATA_COLS = ["_execution_id", "_data_inclusao", "_data_alteracao_silver", "DT_PROCESSAMENTO"]
_KEY_COLS = ["NUM_CPF", "SAFRA"]
_DUPLICATED_COLS = ["FLAG_INSTALACAO", "FPD", "PROD", "flag_mig2"]


def _get_select_cols(df, alias, exclude, prefix=None):
    """Gera lista de colunas formatadas para SQL SELECT.

    Args:
        df: DataFrame Spark.
        alias: Alias da tabela no SQL.
        exclude: Lista de colunas a excluir (case-insensitive).
        prefix: Prefixo opcional para renomear (ex: 'REC').

    Returns:
        list[str]: Colunas formatadas para SQL.
    """
    exclude_lower = {c.lower() for c in exclude}
    cols = []
    for col in df.columns:
        if col.lower() not in exclude_lower:
            if prefix:
                cols.append(f"{alias}.{col} AS {prefix}_{col}")
            else:
                cols.append(f"{alias}.{col}")
    return cols


def build_book_consolidado(spark, safras=None):
    """Constroi feature store consolidada com todas as fontes.

    Executa LEFT JOINs progressivos em (NUM_CPF, SAFRA) partindo de
    dados_cadastrais como tabela base. Books opcionais sao ignorados
    se a tabela Delta nao existir.

    Args:
        spark: SparkSession ativa.
        safras: Lista de safras (int YYYYMM) para filtrar. Se None,
                processa todas as SAFRAs disponiveis na base.

    Returns:
        dict: Metadados com total_registros, total_colunas, fontes.
    """
    if safras is None:
        safras = DEFAULT_SAFRAS

    # Broadcast join threshold (10MB) — consistente com os 3 books individuais
    spark.sql("SET spark.sql.autoBroadcastJoinThreshold = 10485760")
    spark.conf.set("spark.sql.adaptive.enabled", "true")
    spark.conf.set("spark.sql.shuffle.partitions", "200")
    logger.info("autoBroadcastJoinThreshold=10MB, AQE=true, shuffle.partitions=200")

    logger.info("Book Consolidado — carregando fontes...")

    # -------------------------------------------------------------------------
    # CARREGAR TABELAS
    # -------------------------------------------------------------------------
    df_cadastro = spark.read.format("delta").load(PATH_DADOS_CADASTRAIS)
    logger.info("dados_cadastrais: %d cols", len(df_cadastro.columns))

    df_telco = spark.read.format("delta").load(PATH_TELCO)
    logger.info("telco: %d cols", len(df_telco.columns))

    df_score = spark.read.format("delta").load(PATH_SCORE_BUREAU)
    logger.info("score_bureau: %d cols", len(df_score.columns))

    # Books (opcionais)
    from delta.tables import DeltaTable

    books = {}
    for name, path, prefix in [
        ("book_recarga_cmv", PATH_BOOK_RECARGA_CMV, "REC"),
        ("book_pagamento", PATH_BOOK_PAGAMENTO, "PAG"),
        ("book_faturamento", PATH_BOOK_FATURAMENTO, "FAT"),
    ]:
        if DeltaTable.isDeltaTable(spark, path):
            books[name] = {"df": spark.read.format("delta").load(path), "prefix": prefix}
            logger.info("%s: %d cols", name, len(books[name]["df"].columns))
        else:
            logger.warning("%s: NAO encontrado — sera ignorado", name)

    # -------------------------------------------------------------------------
    # REGISTRAR VIEWS
    # -------------------------------------------------------------------------
    df_cadastro.createOrReplaceTempView("dados_cadastrais")
    df_telco.createOrReplaceTempView("telco")
    df_score.createOrReplaceTempView("score_bureau_movel")

    aliases = {"book_recarga_cmv": "r", "book_pagamento": "p", "book_faturamento": "f"}
    for name, info in books.items():
        info["df"].createOrReplaceTempView(name)

    # -------------------------------------------------------------------------
    # CONSTRUIR COLUNAS
    # -------------------------------------------------------------------------
    cols_cadastro = _get_select_cols(df_cadastro, "c", _METADATA_COLS)
    cols_telco = _get_select_cols(df_telco, "t", _METADATA_COLS + _KEY_COLS + _DUPLICATED_COLS)

    # Score: renomear SCORE_ para TARGET_SCORE_
    exclude_score = _METADATA_COLS + _KEY_COLS + _DUPLICATED_COLS
    cols_score = []
    for col in df_score.columns:
        if col.lower() not in {c.lower() for c in exclude_score}:
            if "SCORE_" in col:
                cols_score.append(f"s.{col} AS TARGET_{col}")
            else:
                cols_score.append(f"s.{col}")

    cols_books = {}
    for name, info in books.items():
        alias = aliases[name]
        cols_books[name] = _get_select_cols(
            info["df"], alias, _METADATA_COLS + _KEY_COLS, prefix=info["prefix"]
        )

    # -------------------------------------------------------------------------
    # MONTAR QUERY
    # -------------------------------------------------------------------------
    all_cols = cols_cadastro + cols_telco + cols_score
    for name in ["book_recarga_cmv", "book_pagamento", "book_faturamento"]:
        if name in cols_books:
            all_cols.extend(cols_books[name])
    all_cols.append("CURRENT_TIMESTAMP() AS DT_PROCESSAMENTO")

    columns_sql = ",\n        ".join(all_cols)

    joins_sql = """
    LEFT JOIN telco t ON c.NUM_CPF = t.NUM_CPF AND c.SAFRA = t.SAFRA
    LEFT JOIN score_bureau_movel s ON c.NUM_CPF = s.NUM_CPF AND c.SAFRA = s.SAFRA"""

    if "book_recarga_cmv" in books:
        joins_sql += """
    LEFT JOIN book_recarga_cmv r ON c.NUM_CPF = r.NUM_CPF AND c.SAFRA = r.SAFRA"""
    if "book_pagamento" in books:
        joins_sql += """
    LEFT JOIN book_pagamento p ON c.NUM_CPF = p.NUM_CPF AND c.SAFRA = p.SAFRA"""
    if "book_faturamento" in books:
        joins_sql += """
    LEFT JOIN book_faturamento f ON c.NUM_CPF = f.NUM_CPF AND c.SAFRA = f.SAFRA"""

    # WHERE clause condicional para filtrar SAFRAs
    safra_list = ", ".join(str(s) for s in safras)
    where_sql = f"\nWHERE c.SAFRA IN ({safra_list})"

    query = f"""
SELECT
        {columns_sql}
FROM dados_cadastrais c
{joins_sql}
{where_sql}
"""

    total_cols = len(all_cols)
    logger.info("Query construida — %d colunas esperadas", total_cols)

    # -------------------------------------------------------------------------
    # EXECUTAR E SALVAR
    # -------------------------------------------------------------------------
    try:
        df_result = spark.sql(query)

        total_colunas = len(df_result.columns)
        logger.info("Query executada — %d colunas. Escrevendo em Delta...", total_colunas)

        df_result.write.format("delta") \
            .mode("overwrite") \
            .partitionBy("SAFRA") \
            .option("overwriteSchema", "true") \
            .save(PATH_FEATURE_STORE)

        logger.info("Salvo em: %s", PATH_FEATURE_STORE)

        # ---------------------------------------------------------------------
        # VALIDACAO (leitura pos-escrita, sem cache pre-escrita)
        # ---------------------------------------------------------------------
        df_check = spark.read.format("delta").load(PATH_FEATURE_STORE)
        saved_count = df_check.count()
        saved_cols = len(df_check.columns)

        logger.info("Validacao: %d registros, %d colunas", saved_count, saved_cols)

        # Listar SAFRAs
        safras_saved = [row["SAFRA"] for row in df_check.select("SAFRA").distinct().orderBy("SAFRA").collect()]
        logger.info("SAFRAs: %s", safras_saved)

        metadata = {
            "total_registros": saved_count,
            "total_colunas": saved_cols,
            "safras": safras_saved,
            "fontes": {
                "dados_cadastrais": len(cols_cadastro),
                "telco": len(cols_telco),
                "score_bureau": len(cols_score),
                **{name: len(cols_books.get(name, [])) for name in aliases},
            },
        }

        logger.info("=== Book Consolidado concluido ===")
        return metadata
    except Exception as e:
        logger.error("Book consolidado falhou: %s", e)
        raise


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
build_book_consolidado(spark)
