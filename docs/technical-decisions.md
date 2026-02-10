# Decisoes Tecnicas — Architecture Decision Records

Este documento registra as principais decisoes tecnicas tomadas ao longo do projeto, com contexto, justificativa e consequencias.

---

## ADR-01: Medallion Architecture (Bronze → Silver → Gold)

**Contexto**: Precisavamos de uma arquitetura de dados que suportasse ingestao de multiplas fontes (CSV, Excel, Parquet), limpeza progressiva e feature engineering em grande escala.

**Decisao**: Adotar a Medallion Architecture com 3 camadas, cada uma em um Lakehouse separado no Microsoft Fabric.

**Justificativa**:
- Separacao clara de responsabilidades (raw → cleansed → features)
- Rastreabilidade completa com colunas de auditoria (`_execution_id`, `_data_inclusao`)
- Reprocessamento parcial — nao precisa re-ingerir para recalcular features
- Padrao recomendado pela Microsoft para Delta Lake

**Consequencias**:
- 3 Lakehouses para gerenciar (Bronze, Silver, Gold)
- Cross-lakehouse queries requerem paths completos do OneLake
- Configuracao centralizada em `config/pipeline_config.py` para evitar hardcoding

---

## ADR-02: Delta Lake como Formato de Storage

**Contexto**: Opcoes incluiam Parquet puro, Delta Lake ou Iceberg.

**Decisao**: Delta Lake em todas as camadas.

**Justificativa**:
- Suporte nativo no Microsoft Fabric (otimizado)
- ACID transactions — fundamental para MERGE/UPSERT na Silver
- Time travel — auditoria e rollback de dados
- Schema evolution — adicionar colunas sem recriar tabelas
- Particionamento nativo por SAFRA

**Consequencias**:
- Delta Lake nao suporta Foreign Keys ou indexes nativamente — validacoes sao feitas via PySpark assertions no `utils/data_quality.py`
- MERGE (UPSERT) e a operacao padrao na Silver — evita duplicatas

---

## ADR-03: LEFT JOIN no Consolidado (nao INNER JOIN)

**Contexto**: Ao consolidar os 4 books em `clientes_consolidado`, precisavamos decidir o tipo de JOIN.

**Decisao**: LEFT JOIN em todas as juncoes, partindo de `dados_cadastrais` como base.

**Justificativa**:
- Nem todos os clientes tem dados em todas as fontes (recarga, pagamento, faturamento)
- INNER JOIN eliminaria clientes validos que nao tem, por exemplo, historico de pagamento
- LEFT JOIN preserva todos os clientes elegíveis e trata dados faltantes como NULL
- O modelo lida com NULLs via SimpleImputer(median) no preprocessamento

**Consequencias**:
- Features de fontes secundarias podem ter alto percentual de missing
- Pipeline de feature selection filtra colunas com >50% de missing automaticamente
- Base resultante: 3.9M registros (todos os clientes cadastrados)

---

## ADR-04: Remocao de FAT_VLR_FPD (Data Leakage)

**Contexto**: Durante auditoria, identificamos que `FAT_VLR_FPD` no `book_faturamento` era calculado como `MAX(FPD)` — uma copia direta do target.

**Decisao**: Remover completamente o LEFT JOIN com `dados_cadastrais` do `book_faturamento`, eliminando 12 features que incluiam `FAT_VLR_FPD`.

**Justificativa**:
- Leakage direto: a feature era uma copia do target, inflando artificialmente as metricas
- As outras 11 features do mesmo JOIN tambem eram redundantes (ja presentes na tabela base)
- Remocao preventiva — melhor eliminar do que arriscar contaminacao

**Consequencias**:
- Book faturamento passou de ~120 para 114 features (117 colunas incluindo chaves)
- Modelo baseline NAO foi contaminado — `FAT_VLR_FPD` ja era dropado no treinamento
- DDL do Gold atualizado para refletir a remocao

---

## ADR-05: SCORE_RISCO Mantido (Nao e Leakage)

**Contexto**: `SCORE_RISCO` foi investigado como possivel leakage por conter a palavra "SCORE".

**Decisao**: Manter — nao e leakage.

**Justificativa**:
- `SCORE_RISCO` e calculado a partir de indicadores operacionais: WO (Write-Off), PDD (Provisao), atraso
- Esses indicadores sao dados pre-existentes, nao derivados do FPD
- Feature contribui com 4.7% de importancia SHAP — valor preditivo legítimo

**Consequencias**:
- Feature mantida no modelo como 3a mais importante
- Documentacao explica claramente a diferenca entre FAT_VLR_FPD (leakage) e SCORE_RISCO (nao-leakage)

---

## ADR-06: SAFRA Convertida para INT nos Books

**Contexto**: SAFRA era ingerida como INT na rawdata, mas os SQL templates dos books usavam `'{safra}' AS SAFRA` (string literal), causando inconsistencia de tipo.

**Decisao**: Substituir por `CAST('{safra}' AS INT) AS SAFRA` em todos os books.

**Justificativa**:
- Tipo inconsistente causava erros em JOINs (int vs string)
- Workarounds como `CAST(c.SAFRA AS STRING)` no consolidado eram frageis
- INT e o tipo correto semanticamente (YYYYMM e um numero)

**Consequencias**:
- 3 books atualizados + 3 DDLs
- Removidos workarounds de CAST no consolidado
- JOINs simplificados e consistentes

---

## ADR-07: Split Temporal (nao Cross-Validation)

**Contexto**: Para validacao do modelo, precisavamos escolher entre k-fold cross-validation ou split temporal.

**Decisao**: Split temporal com treino em Q4/2024, validacao em Jan/2025 e teste em Feb-Mar/2025.

**Justificativa**:
- Cross-validation mistura dados futuros no treino — viola causalidade temporal
- Em credit scoring, o modelo e sempre aplicado em dados futuros
- Split temporal simula o cenario real de producao
- OOT (Out-of-Time) e o padrao da industria para validacao de modelos de credito

**Consequencias**:
- Treino: SAFRAs 202410-202412 (~1.35M registros)
- OOS: SAFRA 202501 (~450K) — validacao/hyperparameter tuning
- OOT: SAFRAs 202502-202503 (~870K) — teste final, metricas reportadas

---

## ADR-08: Metricas Rank-Based (KS/AUC/Gini, nao Precision/Recall)

**Contexto**: Escolher quais metricas reportar para o modelo.

**Decisao**: Usar apenas metricas rank-based: KS, AUC-ROC e Gini.

**Justificativa**:
- Em credit scoring, o objetivo e **ordenar** clientes por risco, nao classificar binariamente
- KS mede a maxima separacao entre distribuicoes de bons e maus
- AUC e Gini sao invariantes ao threshold de corte
- Precision/Recall/F1 dependem de um threshold arbitrario e sao instáveis com dados desbalanceados
- Padrao da industria bancaria/telecom para modelos de credito

**Consequencias**:
- Nao reportamos confusion matrix como metrica principal (apenas como visualizacao)
- Threshold de corte e uma decisao de negocio, nao do modelo
- Scoring batch gera probabilidades contínuas (0-1) convertidas para escala 0-1000

---

## ADR-09: Feature Selection em 4 Etapas Sequenciais

**Contexto**: Com 398 features, precisavamos selecionar um subconjunto preditivo sem overfitting.

**Decisao**: Pipeline sequencial de 4 filtros: IV → L1 → Correlacao → LGBM Importance.

**Justificativa**:
- **IV Filter (>0.02)**: Remove features sem poder preditivo univariado
- **L1 Coefficients**: Regularizacao esparsa elimina features redundantes para modelo linear
- **Correlacao (<0.95)**: Remove multicolinearidade severa entre pares
- **LGBM Top 70**: Selecao final baseada em importancia nao-linear

Cada etapa ataca um aspecto diferente da qualidade de features:
- IV: relevancia individual
- L1: redundancia linear
- Correlacao: colinearidade
- LGBM: importancia nao-linear

**Consequencias**:
- 398 → ~59 features finais (reducao de 85%)
- Pipeline reprodutível e auditavel
- SHAP analysis confirma que as 40 features mais importantes capturam ~81% da explicabilidade

---

## ADR-10: Scoring Scale 0-1000 com Faixas de Risco

**Contexto**: Definir como o score seria consumido por sistemas downstream.

**Decisao**: Converter probabilidade (0-1) para escala 0-1000, com 4 faixas de risco.

**Justificativa**:
- Escala 0-1000 e padrao na industria de credito (similar a FICO/Serasa)
- Faixas de risco permitem regras de negocio simples:
  - 0-250: Auto-negacao
  - 250-500: Revisao manual
  - 500-750: Provavelmente aprovar
  - 750-1000: Auto-aprovacao
- Interpretacao intuitiva: score maior = menor risco

**Consequencias**:
- Tabela `Gold.feature_store.clientes_scores` com colunas SCORE (0-1000) e FAIXA_RISCO
- Sistemas de BI/operacoes podem consumir diretamente sem processamento adicional

---

## ADR-11: Monkey-Patch sklearn/LightGBM (Compatibilidade Fabric)

**Contexto**: A versao do scikit-learn no Microsoft Fabric apresentou incompatibilidade com o parametro `force_all_finite` no `check_array()`, causando falha no LightGBM.

**Decisao**: Aplicar monkey-patch que remove os parametros incompatíveis.

**Justificativa**:
- Solucao pragmatica — nao temos controle sobre a versao do sklearn no Fabric
- Pinning de versao (`scikit-learn==1.3.2`) tambem aplicado como defesa em profundidade
- Patch e documentado e reversivel

**Consequencias**:
- Patch aplicado no inicio de todos os notebooks de modelagem
- Necessidade de manter o patch enquanto o Fabric nao atualizar o sklearn
- Documentado para transferencia de conhecimento

---

*Ultima atualizacao: 2026-02-10*
