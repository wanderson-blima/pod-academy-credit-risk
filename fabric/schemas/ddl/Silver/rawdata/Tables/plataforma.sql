CREATE TABLE [rawdata].[plataforma] (

	[COD_PLATAFORMA] bigint NULL, 
	[DSC_PLATAFORMA] varchar(8000) NULL, 
	[DAT_EXPIRACAO_DW] datetime2(6) NULL, 
	[DAT_ATUALIZACAO_DW] datetime2(6) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[DSC_PLATAFORMA_BI] varchar(8000) NULL, 
	[COD_GRUPO_PLATAFORMA_BI] varchar(8000) NULL, 
	[DSC_GRUPO_PLATAFORMA] varchar(8000) NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);