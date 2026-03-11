-- =============================================================================
-- ADW External Tables — OCI Object Storage (Parquet)
-- =============================================================================
-- Creates 32 external tables over Bronze, Silver, and Gold Parquet files.
-- Uses Resource Principal for authentication (no API key credential needed).
--
-- Prerequisites:
--   1. Resource Principal enabled: EXEC DBMS_CLOUD_ADMIN.ENABLE_RESOURCE_PRINCIPAL;
--   2. Dynamic group + IAM policy granting ADW read access to Object Storage
--   3. Orphan Parquet files cleaned (see cleanup_delta_orphans.py)
--   4. ADW has network access to Object Storage (same region: sa-saopaulo-1)
--
-- Notes:
--   - DBMS_CLOUD.CREATE_EXTERNAL_TABLE auto-infers schema from Parquet metadata
--   - Partitioned tables (SAFRA=*) use wildcard in file_uri_list
--   - To recreate, DROP TABLE first: DROP TABLE <name> PURGE;
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- GOLD (1 table) — bucket: pod-academy-gold
-- ─────────────────────────────────────────────────────────────────────────────

-- Gold: clientes_consolidado (402 cols, 3.9M rows, partitioned by SAFRA)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'GOLD_CLIENTES_CONSOLIDADO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-gold/o/feature_store/clientes_consolidado/SAFRA=*/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- ─────────────────────────────────────────────────────────────────────────────
-- SILVER BOOKS (3 tables) — bucket: pod-academy-silver
-- ─────────────────────────────────────────────────────────────────────────────

-- Silver book: ass_recarga_cmv (93 cols, partitioned by SAFRA)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_BOOK_RECARGA_CMV_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/book/ass_recarga_cmv/SAFRA=*/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver book: pagamento (97 cols, partitioned by SAFRA)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_BOOK_PAGAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/book/pagamento/SAFRA=*/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver book: faturamento (117 cols, partitioned by SAFRA)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_BOOK_FATURAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/book/faturamento/SAFRA=*/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- ─────────────────────────────────────────────────────────────────────────────
-- SILVER RAWDATA (19 tables) — bucket: pod-academy-silver
-- ─────────────────────────────────────────────────────────────────────────────

-- Silver rawdata: dados_cadastrais
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_DADOS_CADASTRAIS_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/dados_cadastrais/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: recarga
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_RECARGA_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/recarga/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: pagamento
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_PAGAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/pagamento/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: faturamento
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_FATURAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/faturamento/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: telco
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_TELCO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/telco/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: score_bureau_movel
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_SCORE_BUREAU_MOVEL_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/score_bureau_movel/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: canal_aquisicao_credito
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_CANAL_AQUISICAO_CREDITO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/canal_aquisicao_credito/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: forma_pagamento
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_FORMA_PAGAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/forma_pagamento/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: instituicao
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_INSTITUICAO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/instituicao/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: plano_preco
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_PLANO_PRECO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/plano_preco/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: plataforma
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_PLATAFORMA_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/plataforma/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: promocao_credito
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_PROMOCAO_CREDITO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/promocao_credito/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: status_plataforma
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_STATUS_PLATAFORMA_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/status_plataforma/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: tecnologia
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_TECNOLOGIA_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/tecnologia/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: tipo_credito
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_TIPO_CREDITO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/tipo_credito/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: tipo_faturamento
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_TIPO_FATURAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/tipo_faturamento/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: tipo_insercao
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_TIPO_INSERCAO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/tipo_insercao/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: tipo_recarga
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_TIPO_RECARGA_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/tipo_recarga/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Silver rawdata: dim_calendario
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'SILVER_DIM_CALENDARIO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-silver/o/rawdata/dim_calendario/*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- ─────────────────────────────────────────────────────────────────────────────
-- BRONZE (9 tables) — bucket: pod-academy-bronze
-- NOTE: Bronze has no "staging/" prefix. Files are at root level per table.
-- NOTE: Use part*.parquet (not *.parquet) to avoid _SUCCESS and _delta_log files.
-- NOTE: BRONZE_RECARGA_DIM_EXT fails due to column name exceeding Oracle's
--       128-byte identifier limit — skip or create with explicit column_list.
-- ─────────────────────────────────────────────────────────────────────────────

-- Bronze: dados_cadastrais
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_DADOS_CADASTRAIS_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/dados_cadastrais/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Bronze: recarga
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_RECARGA_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/recarga/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Bronze: pagamento
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_PAGAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/pagamento/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Bronze: faturamento
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_FATURAMENTO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/faturamento/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Bronze: telco
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_TELCO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/telco/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Bronze: score_bureau_movel
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_SCORE_BUREAU_MOVEL_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/score_bureau_movel/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Bronze: recarga_dim (SKIPPED — column name exceeds Oracle identifier limit)
-- To fix: create with explicit column_list that renames the long column.
-- BEGIN
--   DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
--     table_name      => 'BRONZE_RECARGA_DIM_EXT',
--     credential_name => 'OCI$RESOURCE_PRINCIPAL',
--     file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/recarga_dim/part*.parquet',
--     format          => json_object('type' value 'parquet')
--   );
-- END;
-- /

-- Bronze: faturamento_dim
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_FATURAMENTO_DIM_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/faturamento_dim/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- Bronze: dim_calendario
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'BRONZE_DIM_CALENDARIO_EXT',
    credential_name => 'OCI$RESOURCE_PRINCIPAL',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-bronze/o/dim_calendario/part*.parquet',
    format          => json_object('type' value 'parquet')
  );
END;
/

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================
-- After creating all external tables, run these to validate:
--
-- Gold (expected: 3,900,378 rows, but SAFRA column may not appear since it's
-- a Hive-style partition directory, not embedded in the Parquet files):
--   SELECT COUNT(*) FROM GOLD_CLIENTES_CONSOLIDADO_EXT;
--
-- Silver books:
--   SELECT COUNT(*) FROM SILVER_BOOK_RECARGA_CMV_EXT;
--   SELECT COUNT(*) FROM SILVER_BOOK_PAGAMENTO_EXT;
--   SELECT COUNT(*) FROM SILVER_BOOK_FATURAMENTO_EXT;
--
-- List all external tables:
--   SELECT table_name FROM user_tables WHERE table_name LIKE '%_EXT';
--
-- NOTE on SAFRA partition column:
--   Hive-style partitioning (SAFRA=202410/) stores the partition value in the
--   directory name, NOT inside the Parquet file. DBMS_CLOUD.CREATE_EXTERNAL_TABLE
--   does NOT automatically extract partition values from paths.
--   If you need SAFRA as a queryable column, consider:
--     1. The SAFRA column is already embedded in Silver book Parquets (inside the data)
--     2. For Gold, SAFRA is also embedded as a column in the Parquet data
--     3. If not embedded, use DBMS_CLOUD.CREATE_EXTERNAL_PART_TABLE instead
-- =============================================================================
