# Books de Variaveis — Indice

> **Epic**: EPIC-HD-001 | **Stories**: HD-2.1, HD-2.2, HD-2.3

## Visao Geral

Os Books de Variaveis sao tabelas agregadas de features comportamentais, construidas a partir dos dados transacionais Silver e enriquecidas com tabelas dimensionais. Cada book agrega dados por `NUM_CPF + SAFRA` e gera um conjunto de variaveis especificas para o modelo de risco de credito (FPD).

## Books Disponíveis

| Book | Prefixo | Features | Fonte Principal | Documentacao |
|------|---------|----------|-----------------|--------------|
| Recarga CMV | `REC_` | 90 | ass_recarga_cmv_nova (99.9M) | [book-recarga-cmv.md](book-recarga-cmv.md) |
| Pagamento | `PAG_` | 94 | pagamento (27.9M) | [book-pagamento.md](book-pagamento.md) |
| Faturamento | `FAT_` | 114 | dados_faturamento (32.7M) | [book-faturamento.md](book-faturamento.md) |

## Consolidacao

O `book_consolidado` une todos os books via LEFT JOIN em `(NUM_CPF, SAFRA)`:

```
dados_cadastrais (base, 33 vars)
  |-- LEFT JOIN telco                  (66 vars)
  |-- LEFT JOIN score_bureau_movel     (2 targets)
  |-- LEFT JOIN book_recarga_cmv       (REC_, 90 vars)
  |-- LEFT JOIN book_pagamento          (PAG_, 94 vars)
  |-- LEFT JOIN book_faturamento        (FAT_, 114 vars)
  = clientes_consolidado               (402 colunas)
```

**Output**: `Gold.feature_store.clientes_consolidado`
- ~3.9M registros
- 402 colunas (398 features + chaves + auditoria)
- Particionado por SAFRA (202410-202503)

## Score de Risco (por Book)

Cada book gera um SCORE_RISCO proprio (0-100) baseado em indicadores operacionais:

| Score | Componentes | Leakage |
|-------|-------------|---------|
| REC_SCORE_RISCO | Migracao Controle (30%), Status ZB (25%), SOS (20%), Volatilidade (15%), Concentracao (10%) | LIMPO |
| PAG_SCORE_RISCO | Faturas abertas (25%), Juros (25%), Status Baixa (20%), Volatilidade (15%), Multa equip (15%) | LIMPO |
| FAT_SCORE_RISCO | Write-Off (30%), PDD (25%), Atraso 30d (20%), Fraude (15%), ACA (10%) | LIMPO |

> **Nota**: FAT_VLR_FPD foi REMOVIDO do book de faturamento por ser copia direta do target (Story TD-1.1).

## Execucao

```python
# Scripts .py (recomendado para producao)
from book_recarga_cmv import build_book_recarga
from book_pagamento import build_book_pagamento
from book_faturamento import build_book_faturamento

# Ordem de execucao
build_book_recarga(spark)       # 1o
build_book_pagamento(spark)     # 2o
build_book_faturamento(spark)   # 3o
# Depois: book_consolidado.py
```

---
*Hackathon PoD Academy (Claro + Oracle)*
