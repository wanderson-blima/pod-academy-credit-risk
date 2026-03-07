CREATE TABLE [rawdata].[dim_calendario] (

	[DataKey] int NULL, 
	[Data] date NULL, 
	[Ano] int NULL, 
	[AnoMes] varchar(8000) NULL, 
	[NumAnoMes] int NULL, 
	[AnoTrimestre] varchar(8000) NULL, 
	[Mes] int NULL, 
	[NomeMes] varchar(8000) NULL, 
	[NomeMesAbrev] varchar(8000) NULL, 
	[MesAno] varchar(8000) NULL, 
	[Trimestre] int NULL, 
	[SemanaAno] int NULL, 
	[Dia] int NULL, 
	[DiaAno] int NULL, 
	[DiaSemana] int NULL, 
	[NomeDiaSemana] varchar(8000) NULL, 
	[EhFimDeSemana] bit NULL, 
	[EhDiaUtil] bit NULL, 
	[EhHoje] bit NULL, 
	[EhMesAtual] bit NULL, 
	[EhAnoAtual] bit NULL
);