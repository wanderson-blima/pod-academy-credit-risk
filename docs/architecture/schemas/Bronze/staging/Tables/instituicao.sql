CREATE TABLE [staging].[instituicao] (

	[DW_INSTITUICAO] int NULL, 
	[COD_INSTITUICAO] int NULL, 
	[DSC_INSTITUICAO] varchar(8000) NULL, 
	[COD_TIPO_INSTITUICAO] int NULL, 
	[DSC_TIPO_INSTITUICAO] varchar(8000) NULL, 
	[COD_SISTEMA_DW] int NULL, 
	[DAT_EXPIRACAO_DW] varchar(8000) NULL, 
	[DAT_CRIACAO_DW] varchar(8000) NULL, 
	[COD_AGENTE] int NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL
);