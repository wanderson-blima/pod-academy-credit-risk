CREATE TABLE [rawdata].[status_plataforma] (

	[COD_STATUS_PLATAFORMA] varchar(8000) NULL, 
	[DSC_STATUS_PLATAFORMA] varchar(8000) NULL, 
	[IND_ATIVO] varchar(8000) NULL, 
	[DAT_ATUALIZACAO_DW] datetime2(6) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[COD_STATUS_PLAT_GRP] varchar(8000) NULL, 
	[IND_STS_PLAT_GRP_ATIVO] varchar(8000) NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);