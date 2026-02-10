CREATE TABLE [staging].[promocao_credito] (

	[COD_PROMOCAO] int NULL, 
	[DSC_PROMOCAO] varchar(8000) NULL, 
	[DAT_EXPIRACAO_DW] varchar(8000) NULL, 
	[DAT_ATUALIZACAO_DW] varchar(8000) NULL, 
	[DAT_CRIACAO_DW] varchar(8000) NULL, 
	[COD_PROM_GRUPO_CARTAO] int NULL, 
	[DSC_NOME_PROMOCAO] varchar(8000) NULL, 
	[COD_TIPO_PROMOCAO] varchar(8000) NULL, 
	[DAT_INICIO_VIGENCIA] varchar(8000) NULL, 
	[DAT_FIM_VIGENCIA] varchar(8000) NULL, 
	[VAL_PROMOCAO] float NULL, 
	[NUM_CONTA_DEDICADA] int NULL, 
	[_execution_id] varchar(8000) NULL, 
	[_data_inclusao] datetime2(6) NULL
);