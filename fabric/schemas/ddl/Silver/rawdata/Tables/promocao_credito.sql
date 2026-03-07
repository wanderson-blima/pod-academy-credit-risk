CREATE TABLE [rawdata].[promocao_credito] (

	[COD_PROMOCAO] bigint NULL, 
	[DSC_PROMOCAO] varchar(8000) NULL, 
	[DAT_EXPIRACAO_DW] datetime2(6) NULL, 
	[DAT_ATUALIZACAO_DW] datetime2(6) NULL, 
	[DAT_CRIACAO_DW] datetime2(6) NULL, 
	[COD_PROM_GRUPO_CARTAO] bigint NULL, 
	[DSC_NOME_PROMOCAO] varchar(8000) NULL, 
	[COD_TIPO_PROMOCAO] varchar(8000) NULL, 
	[DAT_INICIO_VIGENCIA] datetime2(6) NULL, 
	[DAT_FIM_VIGENCIA] datetime2(6) NULL, 
	[VAL_PROMOCAO] decimal(18,4) NULL, 
	[NUM_CONTA_DEDICADA] bigint NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL, 
	[_data_alteracao_silver] datetime2(6) NULL
);