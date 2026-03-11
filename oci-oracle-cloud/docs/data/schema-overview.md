# Visao Geral do Schema - Arquitetura Medallion

## Resumo do Pipeline

| Camada | Tempo | Tabelas | Volume |
|--------|-------|---------|--------|
| Bronze | 22 min | 19/19 | 163M linhas |
| Silver | 25.5 min | 19/19 | 275K duplicatas removidas |
| Gold | 4h58 | 3 books + consolidado | 3.9M x 402 colunas |
| **Total** | **~5h45** | | |

---

## 1. Bronze (Dados Brutos)

### Descricao

Camada de ingestao: dados carregados de arquivos CSV, Excel e Parquet para o Object Storage bucket `bronze` em formato Delta Lake.

### Tabelas (19)

**7 Tabelas Principais:**

| Tabela | Descricao | Schema |
|--------|-----------|--------|
| dados_cadastrais | Dados cadastrais do cliente | staging |
| telco | Informacoes de telecomunicacao | staging |
| score_bureau_movel | Scores de bureau de credito | staging |
| recarga | Transacoes de recarga | staging |
| pagamento | Transacoes de pagamento | staging |
| faturamento | Dados de faturamento | staging |
| metadados_tabelas | Configuracao de metadados | config |

**12 Tabelas Dimensionais:**

Tabelas de apoio e referencia (dimensoes, lookup, configuracoes adicionais).

### Colunas de Auditoria

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| `_execution_id` | STRING | ID unico da execucao de ingestao |
| `_data_inclusao` | TIMESTAMP | Data/hora de inclusao no Bronze |

### Volume

- **Total**: 163M linhas
- **Formato**: Delta Lake (Parquet + transaction log)
- **Bucket**: `bronze` no Object Storage (`grlxi07jz1mo`)

---

## 2. Silver (Dados Limpos)

### Descricao

Camada de limpeza: tipagem de dados corrigida com base em metadados (`config.metadados_tabelas`), deduplicacao por chave primaria + `_data_inclusao` DESC.

### Processo de Limpeza

1. **Tipagem**: Casting automatico baseado em `config.metadados_tabelas`
   - Tratamento especial de datas no formato `01MAY2024:00:00:00`
2. **Deduplicacao**: Por chave primaria + `_data_inclusao` DESC (mantém registro mais recente)
   - **275K duplicatas removidas**
3. **MERGE**: Delta Lake UPSERT (INSERT ou UPDATE)

### Tabelas (19)

Mesmas 19 tabelas do Bronze, agora no schema `rawdata`.

| Schema | Descricao |
|--------|-----------|
| rawdata | Dados limpos e deduplicados |
| book | Books de features (etapa intermediaria) |

### Colunas de Auditoria Adicionais

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| `_data_alteracao_silver` | TIMESTAMP | Data/hora de alteracao no Silver |

### Volume

- **Bucket**: `silver` no Object Storage
- **Linhas removidas**: 275K duplicatas

---

## 3. Gold (Feature Store)

### Descricao

Camada de features: 3 books de features + tabela consolidada. Todas as features sao calculadas a partir dos dados Silver e agregadas na granularidade `(NUM_CPF, SAFRA)`.

### Books de Features

| Book | Prefixo | Features | Descricao |
|------|---------|----------|-----------|
| book_recarga_cmv | REC_ | 92 | Comportamento de recarga prepaga |
| book_pagamento | PAG_ | 96 | Comportamento de pagamento |
| book_faturamento | FAT_ | 116 | Historico de faturamento |

### Tabela Consolidada: `clientes_consolidado`

| Atributo | Valor |
|----------|-------|
| **Linhas** | 3.900.378 |
| **Colunas** | 402 |
| **Granularidade** | NUM_CPF + SAFRA (YYYYMM) |
| **Particao** | SAFRA (202410 a 202503) |
| **Bucket** | `gold` no Object Storage |

### Composicao das 402 Colunas

| Grupo | Prefixo | Quantidade | Origem |
|-------|---------|------------|--------|
| Cadastro + Telco | (sem prefixo) | ~103 | dados_cadastrais + telco + target |
| Recarga | REC_ | 92 | book_recarga_cmv |
| Pagamento | PAG_ | 96 | book_pagamento |
| Faturamento | FAT_ | 108 | book_faturamento |
| Auditoria | _* | ~3 | Colunas de controle |

---

## 4. Padrao de Join

Todos os joins sao **LEFT JOIN** na chave composta `(NUM_CPF, SAFRA)`:

```
dados_cadastrais (base)
  |-- LEFT JOIN telco ON (NUM_CPF, SAFRA)
  |-- LEFT JOIN score_bureau_movel ON (NUM_CPF, SAFRA)   --> TARGET_SCORE_01, TARGET_SCORE_02, FPD
  |-- LEFT JOIN book_recarga_cmv ON (NUM_CPF, SAFRA)     --> REC_*  (92 features)
  |-- LEFT JOIN book_pagamento ON (NUM_CPF, SAFRA)       --> PAG_*  (96 features)
  |-- LEFT JOIN book_faturamento ON (NUM_CPF, SAFRA)     --> FAT_*  (108 features)
```

### Justificativa do LEFT JOIN

- A tabela `dados_cadastrais` e a base (todos os clientes)
- Nem todos os clientes possuem historico em todos os books
- LEFT JOIN preserva todos os registros da base, preenchendo com NULL onde nao ha dados

---

## 5. Variavel Alvo: FPD

### Definicao

**FPD (First Payment Default)**: Indica se o cliente inadimpliu na sua primeira fatura de telecomunicacao.

### Valores

| Valor | Significado | Descricao |
|-------|-------------|-----------|
| 0 | Adimplente | Pagou a primeira fatura em dia |
| 1 | Inadimplente | Nao pagou a primeira fatura (default) |
| NULL | Sem informacao | Safras recentes sem maturacao suficiente |

### Distribuicao por SAFRA

As safras mais recentes (202502, 202503) podem ter maior proporcao de NULLs por falta de maturacao da informacao de pagamento.

| Safras | Uso no Modelo |
|--------|---------------|
| 202410, 202411, 202412, 202501 | Treinamento (train) |
| 202502, 202503 | Validacao temporal (OOT) |

---

## 6. Granularidade e Particionamento

### Chave de Granularidade

| Campo | Tipo | Descricao |
|-------|------|-----------|
| NUM_CPF | STRING | CPF mascarado (identificador unico do cliente) |
| SAFRA | INTEGER | Ano-mes no formato YYYYMM |

### Particoes

| SAFRA | Periodo |
|-------|---------|
| 202410 | Outubro 2024 |
| 202411 | Novembro 2024 |
| 202412 | Dezembro 2024 |
| 202501 | Janeiro 2025 |
| 202502 | Fevereiro 2025 |
| 202503 | Marco 2025 |

---

## 7. Prefixos de Colunas

| Prefixo | Fonte | Quantidade (Book) | Quantidade (Selecionadas) |
|---------|-------|--------------------|---------------------------|
| (nenhum) | CADASTRO + TELCO + TARGET | ~103 | - |
| REC_ | book_recarga_cmv | 92 | 31 |
| PAG_ | book_pagamento | 96 | 25 |
| FAT_ | book_faturamento | 108 | 36 |
| var_ | score_bureau_movel | - | 19 |
| TARGET_ | score_bureau_movel | - | 2 |

### Convencao de Nomes

As features seguem o padrao: `{PREFIXO}_{METRICA}_{DETALHE}`

Exemplos:
- `REC_QTD_RECARGAS_TOTAL` = Recarga > Quantidade > Recargas Total
- `PAG_VLR_TICKET_MEDIO_CONTRATO` = Pagamento > Valor > Ticket Medio por Contrato
- `FAT_TAXA_ATRASO` = Faturamento > Taxa > Atraso

---

## Coluna de Processamento

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| `DT_PROCESSAMENTO` | TIMESTAMP | Data/hora de processamento na camada Gold |
