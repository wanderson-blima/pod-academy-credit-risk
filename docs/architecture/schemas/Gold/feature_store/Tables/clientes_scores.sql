CREATE TABLE [feature_store].[clientes_scores] (

	[NUM_CPF] varchar(8000) NULL, 
	[SAFRA] int NULL, 
	[SCORE_PROB] float NULL, 
	[SCORE] int NULL, 
	[FAIXA_RISCO] int NULL, 
	[MODEL_NAME] varchar(8000) NULL, 
	[MODEL_VERSION] varchar(8000) NULL, 
	[DT_SCORING] varchar(8000) NULL
);