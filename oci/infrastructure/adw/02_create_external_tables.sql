/*
 * ADW External Tables — Step 2: Create External Tables on Gold Parquet
 * Eliminates data duplication — reads directly from Object Storage
 *
 * Prerequisites: 01_setup_credentials.sql executed successfully
 */

-- Gold Feature Store: clientes_consolidado (468 columns, 3.9M records)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'EXT_GOLD_CLIENTES_CONSOLIDADO',
    credential_name => 'OCI_CRED',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-gold/o/feature_store/clientes_consolidado/*.parquet',
    format          => JSON_OBJECT('type' value 'parquet')
  );
END;
/

-- Gold Feature Store: clientes_final (61 columns — selected features only)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'EXT_GOLD_CLIENTES_FINAL',
    credential_name => 'OCI_CRED',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-gold/o/feature_store/clientes_final/*.parquet',
    format          => JSON_OBJECT('type' value 'parquet')
  );
END;
/

-- Gold Scores: clientes_scores (8 columns)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'EXT_GOLD_CLIENTES_SCORES',
    credential_name => 'OCI_CRED',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-gold/o/clientes_scores/*.parquet',
    format          => JSON_OBJECT('type' value 'parquet')
  );
END;
/

-- Book Recarga (102 columns)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'EXT_GOLD_BOOK_RECARGA',
    credential_name => 'OCI_CRED',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-gold/o/books/book_recarga_cmv/*.parquet',
    format          => JSON_OBJECT('type' value 'parquet')
  );
END;
/

-- Book Pagamento (154 columns)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'EXT_GOLD_BOOK_PAGAMENTO',
    credential_name => 'OCI_CRED',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-gold/o/books/book_pagamento/*.parquet',
    format          => JSON_OBJECT('type' value 'parquet')
  );
END;
/

-- Book Faturamento (108 columns)
BEGIN
  DBMS_CLOUD.CREATE_EXTERNAL_TABLE(
    table_name      => 'EXT_GOLD_BOOK_FATURAMENTO',
    credential_name => 'OCI_CRED',
    file_uri_list   => 'https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/grlxi07jz1mo/b/pod-academy-gold/o/books/book_faturamento/*.parquet',
    format          => JSON_OBJECT('type' value 'parquet')
  );
END;
/

-- Verify tables created
SELECT table_name, num_rows, last_analyzed
FROM user_tables
WHERE table_name LIKE 'EXT_GOLD_%'
ORDER BY table_name;
