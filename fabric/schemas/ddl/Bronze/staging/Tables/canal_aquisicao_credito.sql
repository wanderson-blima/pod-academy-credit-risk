CREATE TABLE [staging].[canal_aquisicao_credito] (

	[COD_CANAL_AQUISICAO] int NULL, 
	[DSC_CANAL_AQUISICAO] varchar(8000) NULL, 
	[COD_SISTEMA_DW] int NULL, 
	[DAT_ATUALIZACAO_DW] varchar(8000) NULL, 
	[DAT_CRIACAO_DW] varchar(8000) NULL, 
	[COD_CANAL_AQUISICAO_BI] int NULL, 
	[DSC_CANAL_AQUISICAO_BI] varchar(8000) NULL, 
	[COD_AGENTE_CREDITO] varchar(8000) NULL, 
	[DAT_EXPIRACAO_DW] varchar(8000) NULL, 
	[COD_TIPO_CREDITO] varchar(8000) NULL, 
	[COD_TIPO_INSTITUICAO] int NULL, 
	[DSC_TIPO_INSTITUICAO] varchar(8000) NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL
);