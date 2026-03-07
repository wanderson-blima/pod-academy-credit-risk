CREATE TABLE [rawdata].[tipo_insercao] (

	[DW_TIPO_INSERCAO] int NULL, 
	[DSC_TIPO_INSERCAO] varchar(8000) NULL, 
	[DAT_EXPIRACAO_DW] datetime2(6) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);