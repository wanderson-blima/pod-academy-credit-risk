CREATE TABLE [rawdata].[forma_pagamento] (

	[DW_FORMA_PAGAMENTO] bigint NULL, 
	[COD_FORMA_PAGAMENTO] varchar(8000) NULL, 
	[DSC_FORMA_PAGAMENTO] varchar(8000) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[DAT_EXPIRACAO_DW] datetime2(6) NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);