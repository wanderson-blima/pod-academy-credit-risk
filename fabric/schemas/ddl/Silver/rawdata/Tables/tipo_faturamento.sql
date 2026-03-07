CREATE TABLE [rawdata].[tipo_faturamento] (

	[DW_TIPO_FATURAMENTO] int NULL, 
	[DSC_TIPO_FATURAMENTO] varchar(8000) NULL, 
	[COD_TIPO_FATURAMENTO] varchar(8000) NULL, 
	[DAT_EXPIRACAO_DW] datetime2(6) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[DSC_TIPO_FATURAMENTO_ABREV] varchar(8000) NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);