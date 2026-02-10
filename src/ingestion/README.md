# Stage 1 — Ingestao de Dados

Responsavel por carregar arquivos de diversas fontes (CSV, Excel, Parquet) para o **Bronze Lakehouse** (staging).

## Scripts

| Script | Descricao |
|--------|-----------|
| [`ingestao-arquivos.py`](ingestao-arquivos.py) | Pipeline de ingestao batch com reader hibrido Pandas+Spark |
| [`criacao-dimensoes.py`](criacao-dimensoes.py) | Criacao de tabelas dimensionais (calendario, CPF) |

## Como Funciona

### Ingestao (`ingestao-arquivos.py`)

1. Leitura hibrida: Pandas para Excel, Spark para CSV/Parquet
2. Cada execucao gera um `_execution_id` unico para rastreabilidade
3. Coluna `_data_inclusao` registra o timestamp de ingestao
4. Dados sao escritos em Delta Lake no schema `staging` do Bronze
5. Erros e estatisticas sao logados na tabela `log.log_info`

**Configuracao por tabela** via dicionario `params`:

```python
params = {
    "source_format": "excel|csv|parquet",
    "source_folder": "Files/...",
    "target_schema": "staging|config",
    "target_table": "table_name",
    "options": {"header": "true", "delimiter": ";"}
}
```

### Dimensoes (`criacao-dimensoes.py`)

- `dim_calendario`: Tabela de datas com atributos (ano, mes, trimestre, dia util)
- `dim_num_cpf`: Surrogate key para CPF mascarado (NUM_CPF → SK)
- Operacao idempotente — recria se ja existir

## Decisoes

- **Por que Pandas + Spark?** Excel nao e suportado nativamente pelo Spark. Pandas le Excel e converte para Spark DataFrame.
- **Por que `_execution_id`?** Permite rastrear quais registros vieram de qual execucao e facilita reprocessamento parcial.
- **Por que Delta Lake?** ACID transactions garantem que ingestoes parciais nao corrompam os dados.

## Destino

```
Bronze Lakehouse (b8822164...)
├── staging/          ← dados ingeridos (19 tabelas)
├── config/           ← metadados de configuracao
└── log/              ← log de execucao
```

---

*Veja tambem: [Arquitetura de Dados](../../docs/architecture/data-architecture.md)*
