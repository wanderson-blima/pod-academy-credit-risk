# Stage 4 — Feature Engineering (Books)

Responsavel pela construcao de features a partir dos dados limpos (Silver rawdata), gerando books tematicos que sao consolidados no **Gold Lakehouse** (feature_store).

## Scripts

| Script | Features | Prefixo | Descricao |
|--------|----------|---------|-----------|
| [`book_recarga_cmv.py`](book_recarga_cmv.py) | 90 | `REC_` | Comportamento de recarga (frequencia, valores, canais) |
| [`book_pagamento.py`](book_pagamento.py) | 94 | `PAG_` | Comportamento de pagamento (faturas, atrasos, valores) |
| [`book_faturamento.py`](book_faturamento.py) | 114 | `FAT_` | Dados de faturamento (ciclos, isencoes, vencimentos) |
| [`book_consolidado.py`](book_consolidado.py) | 402 | — | Consolidacao de todos os books + cadastro |

## Arquitetura de Features

### Padrao de Construcao

Cada book segue o mesmo padrao:

1. **SQL Template** — Query parametrizada por `{safra}` que agrega dados transacionais
2. **Agregacao por (NUM_CPF, SAFRA)** — Uma linha por cliente por periodo
3. **Metricas calculadas** — Contagens, medias, desvios, taxas, maximos, minimos
4. **Escrita em Delta** — Silver.book.{nome_do_book}

```python
for safra in SAFRAS:
    query = sql_template.format(safra=safra)
    df = spark.sql(query)
    df.write.format("delta").mode("append").saveAsTable(...)
```

### Consolidacao

O `book_consolidado.py` une todos os books via LEFT JOIN:

```
dados_cadastrais (base, 33 vars)
  ├── LEFT JOIN telco               ON (NUM_CPF, SAFRA)  → 66 vars
  ├── LEFT JOIN score_bureau_movel  ON (NUM_CPF, SAFRA)  → 2 targets
  ├── LEFT JOIN book_recarga_cmv    ON (NUM_CPF, SAFRA)  → 90 vars (REC_*)
  ├── LEFT JOIN book_pagamento      ON (NUM_CPF, SAFRA)  → 94 vars (PAG_*)
  └── LEFT JOIN book_faturamento    ON (NUM_CPF, SAFRA)  → 114 vars (FAT_*)
```

**Resultado**: `Gold.feature_store.clientes_consolidado` — 3.9M registros, 402 colunas

### Tipos de Features Calculadas

| Tipo | Exemplos | Logica |
|------|---------|--------|
| Contagens | `REC_QTD_RECARGAS_TOTAL` | COUNT de transacoes |
| Valores | `PAG_VLR_PAGAMENTO_FATURA_MEDIA` | AVG de valores |
| Variabilidade | `REC_VLR_REAL_STDDEV` | STDDEV de valores |
| Taxas | `REC_TAXA_STATUS_A` | COUNT(status=A) / COUNT(*) |
| Temporais | `REC_DIAS_ENTRE_RECARGAS` | Dias entre eventos |
| Scores | `REC_SCORE_RISCO` | Score agregado de risco operacional |

## Decisoes

- **Por que LEFT JOIN e nao INNER?** Nem todos os clientes tem dados em todas as fontes. LEFT JOIN preserva a base completa.
- **Por que prefixos (REC_, PAG_, FAT_)?** Evita conflito de nomes e facilita identificacao da origem de cada feature.
- **Por que SAFRA como particao?** Permite processamento incremental — apenas novas SAFRAs sao calculadas.
- **Leakage removido**: `FAT_VLR_FPD` era `MAX(FPD)` — copia direta do target. JOIN com `dados_cadastrais` foi removido do book_faturamento. Ver [ADR-04](../../docs/technical-decisions.md#adr-04-remocao-de-fat_vlr_fpd-data-leakage).

## Destino

```
Silver Lakehouse (5f8a4808...)
└── book/            ← books individuais (3 tabelas)

Gold Lakehouse (6a7135c7...)
└── feature_store/   ← clientes_consolidado (402 colunas) + clientes_scores (8 colunas)
```

---

*Documentacao detalhada das variaveis: [docs/feature-engineering/](../../docs/feature-engineering/)*
