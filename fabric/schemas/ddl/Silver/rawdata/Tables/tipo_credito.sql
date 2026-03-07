CREATE TABLE [rawdata].[tipo_credito] (

	[COD_TIPO_CREDITO] varchar(8000) NULL, 
	[DSC_TIPO_CREDITO] varchar(8000) NULL, 
	[DAT_EXPIRACAO_DW] datetime2(6) NULL, 
	[DAT_ATUALIZACAO_DW] datetime2(6) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);