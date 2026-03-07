CREATE TABLE [rawdata].[instituicao] (

	[DW_INSTITUICAO] bigint NULL, 
	[COD_INSTITUICAO] varchar(8000) NULL, 
	[DSC_INSTITUICAO] varchar(8000) NULL, 
	[COD_TIPO_INSTITUICAO] int NULL, 
	[DSC_TIPO_INSTITUICAO] varchar(8000) NULL, 
	[COD_SISTEMA_DW] int NULL, 
	[DAT_EXPIRACAO_DW] datetime2(6) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[COD_AGENTE] bigint NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);