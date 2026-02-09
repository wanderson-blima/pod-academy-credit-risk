"""
Configuracao centralizada do pipeline de dados - Hackathon PoD Academy.

Todas as constantes de ambiente (Lakehouse IDs, paths OneLake, schemas)
devem ser importadas deste modulo. Nenhum script/notebook deve ter IDs hardcoded.

Uso:
    from config.pipeline_config import *
    # ou
    from config.pipeline_config import SILVER_BASE, BRONZE_BASE, GOLD_BASE
"""

# =============================================================================
# LAKEHOUSE IDs
# =============================================================================
WORKSPACE_ID = "febb8631-d5c0-43d8-bf08-5e89c8f2d17e"
BRONZE_ID = "b8822164-7b67-4b17-9a01-3d0737dace7e"
SILVER_ID = "5f8a4808-6f65-401b-a427-b0dd9d331b35"
GOLD_ID = "6a7135c7-0d8d-4625-815d-c4c4a02e4ed4"

# =============================================================================
# ONELAKE BASE PATHS
# =============================================================================
_ONELAKE_PREFIX = f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com"

BRONZE_BASE = f"{_ONELAKE_PREFIX}/{BRONZE_ID}"
SILVER_BASE = f"{_ONELAKE_PREFIX}/{SILVER_ID}"
GOLD_BASE = f"{_ONELAKE_PREFIX}/{GOLD_ID}"

# =============================================================================
# SCHEMA NAMES
# =============================================================================
SCHEMA_STAGING = "staging"
SCHEMA_CONFIG = "config"
SCHEMA_LOG = "log"
SCHEMA_RAWDATA = "rawdata"
SCHEMA_BOOK = "book"
SCHEMA_FEATURE_STORE = "feature_store"

# =============================================================================
# COMMON TABLE PATHS
# =============================================================================

# Bronze
PATH_METADATA_TABLE = f"{BRONZE_BASE}/Tables/{SCHEMA_CONFIG}/metadados_tabelas"
PATH_LOG = f"{BRONZE_BASE}/Tables/{SCHEMA_LOG}/log_info"

# Silver - Raw
PATH_DADOS_CADASTRAIS = f"{SILVER_BASE}/Tables/{SCHEMA_RAWDATA}/dados_cadastrais"
PATH_TELCO = f"{SILVER_BASE}/Tables/{SCHEMA_RAWDATA}/telco"
PATH_SCORE_BUREAU = f"{SILVER_BASE}/Tables/{SCHEMA_RAWDATA}/score_bureau_movel_full"
PATH_DIM_CALENDARIO = f"{SILVER_BASE}/Tables/{SCHEMA_RAWDATA}/dim_calendario"
PATH_DIM_NUM_CPF = f"{SILVER_BASE}/Tables/{SCHEMA_RAWDATA}/dim_num_cpf"

# Silver - Books
PATH_BOOK_RECARGA_CMV = f"{SILVER_BASE}/Tables/{SCHEMA_BOOK}/ass_recarga_cmv"
PATH_BOOK_PAGAMENTO = f"{SILVER_BASE}/Tables/{SCHEMA_BOOK}/pagamento"
PATH_BOOK_FATURAMENTO = f"{SILVER_BASE}/Tables/{SCHEMA_BOOK}/faturamento"

# Gold
PATH_FEATURE_STORE = f"{GOLD_BASE}/Tables/{SCHEMA_FEATURE_STORE}/clientes_consolidado"


# =============================================================================
# SAFRAS (processing periods — YYYYMM)
# =============================================================================
SAFRAS = [202410, 202411, 202412, 202501, 202502, 202503]

# =============================================================================
# SILVER PROCESSING — tables to cast + deduplicate
# =============================================================================
SILVER_TABLES = ["score_bureau_movel_full", "dados_cadastrais", "telco"]

# =============================================================================
# MLFLOW
# =============================================================================
EXPERIMENT_NAME = "credit-risk-ds"
REGISTERED_MODEL_NAME = "credit-risk-fpd-lgbm_baseline"

# =============================================================================
# SPARK PERFORMANCE TUNING
# =============================================================================
SPARK_BROADCAST_THRESHOLD = 52428800   # 50MB — broadcast JOINs para dimensoes
SPARK_SHUFFLE_PARTITIONS = 200         # AQE shuffle partitions default
SPARK_AQE_ENABLED = True               # Adaptive Query Execution

# =============================================================================
# DATA QUALITY CONFIG
# =============================================================================
LEAKAGE_BLACKLIST = ["FAT_VLR_FPD"]
TARGET_COLUMNS = ["FPD", "TARGET_SCORE_01", "TARGET_SCORE_02"]
EXPECTED_FEATURES = {
    "ass_recarga_cmv": 102,
    "pagamento": 154,
    "faturamento": 108,
    "clientes_consolidado": 468,
}

# =============================================================================
# INGESTION PARAMS — batch list (add entries as needed)
# =============================================================================
INGESTION_PARAMS = [
    {
        "source_format": "excel",
        "source_folder": "Files/meta_dados_analise.xlsx",
        "target_schema": "config",
        "target_table": "metadados_tabelas",
        "options": {"dataAddress": "'info'!A1", "header": "true"},
    },
    {
        "source_format": "csv",
        "source_folder": "Files/bases_cadastro/dados_cadastrais",
        "target_schema": "staging",
        "target_table": "dados_cadastrais",
        "options": {"header": "true", "delimiter": ",", "inferSchema": "true", "encoding": "UTF-8"},
    },
    {
        "source_format": "csv",
        "source_folder": "Files/bases_cadastro/telco",
        "target_schema": "staging",
        "target_table": "telco",
        "options": {"header": "true", "delimiter": ",", "inferSchema": "true", "encoding": "UTF-8"},
    },
    {
        "source_format": "parquet",
        "source_folder": "Files/base_score_bureau_movel_full",
        "target_schema": "staging",
        "target_table": "score_bureau_movel_full",
        "options": {"header": "true", "inferSchema": "true"},
    },
    {
        "source_format": "csv",
        "source_folder": "Files/bases_recarga/ass_recarga_cmv_nova",
        "target_schema": "staging",
        "target_table": "ass_recarga_cmv_nova",
        "options": {"header": "true", "delimiter": ",", "inferSchema": "true", "encoding": "UTF-8"},
    },
    {
        "source_format": "csv",
        "source_folder": "Files/bases_pagamento/pagamento",
        "target_schema": "staging",
        "target_table": "pagamento",
        "options": {"header": "true", "delimiter": ",", "inferSchema": "true", "encoding": "UTF-8"},
    },
    {
        "source_format": "csv",
        "source_folder": "Files/bases_faturamento/dados_faturamento",
        "target_schema": "staging",
        "target_table": "dados_faturamento",
        "options": {"header": "true", "delimiter": ",", "inferSchema": "true", "encoding": "UTF-8"},
    },
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_staging_path(table_name):
    """Retorna o path de uma tabela no schema staging (Bronze)."""
    return f"{BRONZE_BASE}/Tables/{SCHEMA_STAGING}/{table_name}"


def get_rawdata_path(table_name):
    """Retorna o path de uma tabela no schema rawdata (Silver)."""
    return f"{SILVER_BASE}/Tables/{SCHEMA_RAWDATA}/{table_name}"


def get_book_path(table_name):
    """Retorna o path de uma tabela no schema book (Silver)."""
    return f"{SILVER_BASE}/Tables/{SCHEMA_BOOK}/{table_name}"
