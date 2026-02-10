CREATE TABLE [log].[log_info] (

	[EndTime] datetime2(6) NULL, 
	[ErrorMessage] varchar(8000) NULL, 
	[ExecutionId] varchar(8000) NULL, 
	[RowsAffected] bigint NULL, 
	[Schema] varchar(8000) NULL, 
	[StartTime] datetime2(6) NULL, 
	[Status] varchar(8000) NULL, 
	[TableName] varchar(8000) NULL
);