# PRD — Migrar Pipeline de Dados Fabric para OCI (Paridade Completa)

## Context

O pipeline de risco de credito roda no Microsoft Fabric com arquitetura medalhao (Bronze > Silver > Gold) produzindo um feature store de **402 colunas** e **~3.9M linhas**. A infraestrutura OCI ja esta provisionada (VCN, buckets, Data Flow, ADW). Uma primeira execucao do pipeline na OCI foi feita em 2026-02-16 com sucesso parcial:

- **Bronze**: OK (9 tabelas ingeridas, 9.84 GB)
- **Silver**: Parcial (7 tabelas de rawdata, books com dados BRUTOS nao agregados)
- **Gold**: 104 colunas vs 402 esperadas (faltam REC_*, PAG_*, FAT_*)

**Causa raiz**: O script `engineer_gold.py` v5 que rodou fazia joins simples sem a logica de agregacao dos books. O script v6 em `squads/oci-data-platform/scripts/pipeline/engineer_gold.py` **ja contem os SQL templates completos** (3 books com toda a logica de agregacao) mas **nunca foi deployed/executado**.

**Objetivo**: Executar o pipeline completo com paridade exata ao Fabric — mesmas tabelas, mesmas linhas, mesmas colunas, mesma logica de transformacao.

**Trial Credit**: US$ 500 (creditos Oracle hackathon). Custo real do Data Flow: **$0.025/OCPU-hora** + $0.0015/GB-hora. Custos reportados em BRL na regiao sa-saopaulo-1.

---

## Gap Analysis

### O que JA funciona na OCI

| Componente | Script | Status |
|------------|--------|--------|
| Bronze ingestion (9 tabelas) | `pipeline/ingest_bronze.py` | FUNCIONA — testado v2 |
| Silver transform (7 tabelas) | `pipeline/transform_silver.py` | FUNCIONA — testado v3 |
| SQL Template Book Recarga (~93 cols) | `pipeline/engineer_gold.py` v6 SQL_RECARGA | ESCRITO — nao executado |
| SQL Template Book Pagamento (~97 cols) | `pipeline/engineer_gold.py` v6 SQL_PAGAMENTO | ESCRITO — nao executado |
| SQL Template Book Faturamento (~117 cols) | `pipeline/engineer_gold.py` v6 SQL_FATURAMENTO | ESCRITO — nao executado |
| Consolidacao Gold com prefixos REC_/PAG_/FAT_ | `pipeline/engineer_gold.py` v6 | ESCRITO — nao executado |

### Gaps a resolver

| # | Gap | Impacto | Prioridade |
|---|-----|---------|------------|
| G1 | Silver: falta type casting metadata-driven | Tipos podem estar errados | ALTA |
| G2 | Silver: falta processar 11 tabelas de dimensao (paridade Fabric) | Silver diverge do Fabric | ALTA |
| G3 | Gold v6: nunca deployed/executado no Data Flow | Gold com 104/402 cols | CRITICA |
| G4 | Spark sizing: recarga 99M linhas, precisa mais compute | Risco OOM/timeout | CRITICA |
| G5 | Validacao: nao existe modulo de data quality no OCI | Sem garantia paridade | ALTA |

---

## Spark Architecture — Sizing Otimizado (Pesquisa OCI Data Flow)

### Pricing Real (sa-saopaulo-1)

| Shape | OCPU/hora | Memoria/GB/hora | Nota |
|-------|-----------|-----------------|------|
| VM.Standard.E4.Flex | **$0.025** | **$0.0015** | Shape atual, comprovado |

**Importante**: O Data Flow nao tem surcharge — so paga compute. O report anterior estimava $0.30/OCPU-hora, mas o custo real e **12x menor**.

### Config por Tipo de Run (run-level override)

O Data Flow permite configurar driver/executor **por run**, nao apenas por pool. Estrategia tiered:

| Run | Driver | Executors | Total OCPUs | Custo/hora |
|-----|--------|-----------|-------------|------------|
| **Bronze/Silver** | 2 OCPU, 16 GB | 1x (2 OCPU, 16 GB) | 4 | ~$0.15/hr |
| **Gold (books + consolidacao)** | 2 OCPU, 16 GB | 3x (4 OCPU, 32 GB) | 14 | ~$0.52/hr |

### Spark Configs para Gold (agregacao massiva)

```python
spark_config = {
    # AQE — CRITICO para GROUP BY
    "spark.sql.adaptive.enabled": "true",
    "spark.sql.adaptive.coalescePartitions.enabled": "true",
    "spark.sql.adaptive.coalescePartitions.parallelismFirst": "false",
    "spark.sql.adaptive.advisoryPartitionSizeInBytes": "128MB",
    "spark.sql.adaptive.skewJoin.enabled": "true",

    # Shuffle (100 por SAFRA iteration, nao 200)
    "spark.sql.shuffle.partitions": "100",

    # Broadcast dims (<50MB cada, total <350MB)
    "spark.sql.autoBroadcastJoinThreshold": "104857600",  # 100MB

    # Memory tuning (mais execucao, menos cache)
    "spark.memory.fraction": "0.8",
    "spark.memory.storageFraction": "0.2",

    # Serialization + IO
    "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
    "spark.hadoop.fs.oci.io.read.buffer.size": "8388608",  # 8MB
}
```

### Estimativa de Custo por Pipeline Run

| Stage | Config | Duracao | Custo |
|-------|--------|---------|-------|
| Bronze | 4 OCPUs, 32 GB | ~35 min | ~$0.06 |
| Silver | 4 OCPUs, 32 GB | ~30 min | ~$0.05 |
| Gold (books + consolidacao) | 14 OCPUs, 112 GB | ~43 min | ~$0.37 |
| **Total por run** | | **~108 min** | **~$0.48** |

**Trial credit: US$ 500 permite ~1.000 runs completos.** Extremamente confortavel para desenvolvimento, teste e producao. Na pratica, o Data Flow consumiu R$ 42.29 em 23 runs.

### Pool Config Recomendado

```
Shape: VM.Standard.E4.Flex
Min nodes: 0 (zero custo idle)
Max nodes: 16
Idle timeout: 30 min
```

---

## Epic: OCI-PIPE-001 — Pipeline Medallion com Paridade Fabric

**Goal**: Bronze > Silver > Gold no OCI com 402 colunas, ~3.9M linhas, 6 SAFRAs.
**Execucao**: Continua (stories em sequencia, sem pausa entre elas).

---

### Story 1: Corrigir Silver Transform — Type Casting + 11 Dimensoes

**Owner**: `@data-engineer (Flux)`
**Prioridade**: ALTA
**Status**: IMPLEMENTADO

**Descricao**: O `transform_silver.py` atual processa 7 tabelas sem type casting e sem dimensoes.

**Tarefas**:

1. **Adicionar type casting metadata-driven**: Portar logica de `src/metadata/ajustes-tipagem-deduplicacao.py` como dicionario hardcoded no script (pragmatico — evita portar tabela metadados).
   - SAFRA -> int, VAL_* -> double, DAT_* -> date/timestamp, FPD -> int, etc.
   - Custom date: `01MAY2024:00:00:00` -> `to_timestamp(col, 'ddMMMyyyy:HH:mm:ss')`

2. **Adicionar 12 tabelas de dimensao ao manifest**: `canal_aquisicao_credito`, `forma_pagamento`, `instituicao`, `plano_preco`, `plataforma`, `promocao_credito`, `status_plataforma`, `tecnologia`, `tipo_credito`, `tipo_faturamento`, `tipo_insercao`, `tipo_recarga`.
   - Ler do landing CSVs (recarga_dim/ e faturamento_dim/) com fallback para Bronze
   - Escrever em `Silver/rawdata/{table_name}/`

3. **PKs corretas para dedup**: Mapear PKs do metadados Fabric por tabela. Transacionais = dropDuplicates() full-row.

**Criterios de Aceite**:
- [x] 19 tabelas no Silver rawdata (7 principais + 12 dimensoes)
- [x] Tipos corretos conforme metadados Fabric
- [x] Row counts == Fabric baseline (tolerancia 0.1%)

**Arquivo**: `squads/oci-data-platform/scripts/pipeline/transform_silver.py`
**Referencia**: `src/metadata/ajustes-tipagem-deduplicacao.py`

---

### Story 2: Aplicar Spark Tuning no engineer_gold.py v6

**Owner**: `@data-engineer (Flux)` + `@cloud-ops (Nimbus)`
**Prioridade**: CRITICA
**Status**: IMPLEMENTADO

**Descricao**: Configurar o engineer_gold.py v6 com Spark tuning otimizado para processar 99M+ linhas.

**Tarefas**:

1. **Atualizar SparkSession config** no engineer_gold.py com os Spark configs pesquisados (AQE, broadcast 100MB, shuffle 100, memory 0.8/0.2, Kryo, OCI IO buffer).

2. **Verificar Data Flow pool** suporta shape E4.Flex com max=16 nodes.

3. **Preparar comando de submissao** com run-level override:
   ```
   --driver-shape-config '{"ocpus":2,"memoryInGBs":16}'
   --executor-shape-config '{"ocpus":4,"memoryInGBs":32}'
   --num-executors 3
   ```

4. **Teste com 1 SAFRA**: Modificar SAFRAS = [202410], rodar, validar que nao da OOM e que os books tem as colunas corretas.

**Criterios de Aceite**:
- [x] Spark configs aplicados no script
- [x] Leakage blacklist (FAT_VLR_FPD) adicionada
- [x] Validation prints no summary (SAFRA count, TARGET_SCORE, leakage check)
- [ ] Teste 1-SAFRA executado sem OOM
- [ ] Books com colunas corretas no teste

**Arquivo**: `squads/oci-data-platform/scripts/pipeline/engineer_gold.py`

---

### Story 3: Deploy e Execucao Completa Gold v6 (402 Colunas)

**Owner**: `@data-engineer (Flux)`
**Prioridade**: CRITICA
**Status**: PRONTO PARA DEPLOY

**Descricao**: Upload, deploy e execucao do engineer_gold.py v6 com todos os 6 SAFRAs.

**Passos**:

1. **Upload** do script v6 para scripts bucket
2. **Atualizar Data Flow application** com novo file URI
3. **Executar com 6 SAFRAs** e config de compute da Story 2
4. **Verificar output**:
   - Silver books: recarga ~93 cols, pagamento ~97 cols, faturamento ~117 cols
   - Gold: clientes_consolidado 402 cols, 3.900.378 rows, 6 SAFRAs

**Criterios de Aceite**:
- [ ] 3 Silver books com colunas agregadas (nao mais dados brutos)
- [ ] Gold clientes_consolidado: **402 colunas exatas**
- [ ] **3.900.378 linhas**
- [ ] 6 particoes SAFRA (202410-202503)
- [ ] Prefixos corretos: REC_*, PAG_*, FAT_*
- [ ] TARGET_SCORE_01/02 (nao SCORE_01/02)
- [ ] FAT_VLR_FPD AUSENTE
- [ ] Sem duplicatas em (NUM_CPF, SAFRA)

**Arquivo**: `squads/oci-data-platform/scripts/pipeline/engineer_gold.py` (v6, ja existe)

---

### Story 4: Validacao de Paridade End-to-End (OCI vs Fabric)

**Owner**: `@data-engineer (Flux)` + Atlas (OCI Chief)
**Prioridade**: ALTA
**Status**: IMPLEMENTADO

**Descricao**: Criar e executar validacao automatizada.

**Checks**:

| Camada | Check | Baseline Fabric |
|--------|-------|-----------------|
| Bronze | 9 tabelas presentes | 9 tabelas |
| Silver rawdata | 19 tabelas | dados_cadastrais=3.900.378, recarga=99.896.314, pagamento=27.948.583, faturamento=32.687.219 |
| Silver book | recarga 93 cols, pagamento 97 cols, faturamento 117 cols | Agregados por (NUM_CPF, SAFRA) |
| Gold | 402 colunas, 3.900.378 rows, 6 SAFRAs | Paridade total |
| Gold | FAT_VLR_FPD ausente | Leakage fix confirmado |
| Gold | Null rates comparaveis | Tolerancia 5pp |

**Criterios de Aceite**:
- [x] Script de validacao criado
- [ ] Script de validacao executado
- [ ] Relatorio de paridade: PASS em todos os checks
- [ ] Row counts match (tolerancia 0.1%)
- [ ] Column counts match (exato)

**Arquivo criado**: `squads/oci-data-platform/scripts/pipeline/validate_parity.py`

---

## Agent Assignments (Squad OCI Data Platform)

| Story | Agent Primario | Agent Suporte | Skill Command |
|-------|---------------|---------------|---------------|
| Story 1: Fix Silver | `@data-engineer (Flux)` | -- | `/oci-data-platform:data-engineer` |
| Story 2: Spark Tuning | `@data-engineer (Flux)` | `@cloud-ops (Nimbus)` | `/oci-data-platform:data-engineer` |
| Story 3: Deploy Gold v6 | `@data-engineer (Flux)` | `@cloud-ops (Nimbus)` | `/oci-data-platform:data-engineer` |
| Story 4: Validacao | `@data-engineer (Flux)` | Atlas (OCI Chief) | `/oci-data-platform:oci-chief` |

---

## Ordem de Execucao

```
Story 1 (Fix Silver) ----+
                          +--> Story 3 (Deploy Gold v6) --> Story 4 (Validacao)
Story 2 (Spark tuning) --+
```

Stories 1 e 2 em paralelo. Story 3 depende de ambas. Story 4 depende de 3.

---

## Verificacao (Como testar)

1. **Apos Story 1**: `oci os object list --bucket-name pod-academy-silver --prefix rawdata/` — 19 tabelas
2. **Apos Story 2**: Teste 1-SAFRA no Data Flow sem OOM
3. **Apos Story 3**: Download Parquet sample do Gold e verificar schema com pyarrow (402 colunas)
4. **Apos Story 4**: Relatorio markdown PASS/FAIL

---

## Arquivos Criticos

| Arquivo | Path | Acao |
|---------|------|------|
| Bronze ingestion | `squads/oci-data-platform/scripts/pipeline/ingest_bronze.py` | Sem alteracao |
| Silver transform | `squads/oci-data-platform/scripts/pipeline/transform_silver.py` | MODIFICADO (Story 1) |
| Gold feature eng. | `squads/oci-data-platform/scripts/pipeline/engineer_gold.py` | TUNING (Story 2) + DEPLOY (Story 3) |
| Validacao | `squads/oci-data-platform/scripts/pipeline/validate_parity.py` | CRIADO (Story 4) |
| Fabric book recarga | `src/feature-engineering/book_recarga_cmv.py` | REFERENCIA |
| Fabric book pagamento | `src/feature-engineering/book_pagamento.py` | REFERENCIA |
| Fabric book faturamento | `src/feature-engineering/book_faturamento.py` | REFERENCIA |
| Fabric consolidado | `src/feature-engineering/book_consolidado.py` | REFERENCIA |
| Gold DDL (402 cols) | `docs/architecture/schemas/Gold/feature_store/Tables/clientes_consolidado.sql` | REFERENCIA |
| Pipeline config | `config/pipeline_config.py` | REFERENCIA |
