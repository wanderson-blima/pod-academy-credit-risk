# Metodologia de Pre-processamento

> Story: HD-3.4 | Epic: EPIC-HD-001 | Entregavel: D

## 1. Visao Geral do Pipeline

Pipeline de preparacao de dados para modelo de risco de credito (FPD) para clientes Claro migrando de PRE para CONTROLE.

### Etapas do Pre-processamento

```mermaid
graph LR
    A["Dados Brutos<br/>468 features"] --> B["Limpeza<br/>Chaves/Datas"]
    B --> C["Missing Filter<br/><70%"]
    C --> D["Cardinalidade<br/>Remove constantes"]
    D --> E["Split Estratificado<br/>75% treino"]
    E --> F["Correlacao<br/><0.80"]
    F --> G["Encoding<br/>CEP→UF→Regiao"]
    G --> H["Features Finais"]
```

### Funcoes Implementadas

| Funcao | Arquivo | Descricao |
|--------|---------|-----------|
| `clean_empty_keys_data()` | modelo_baseline | Remove colunas de chave (NUM_CPF) e metadados |
| `remove_high_missing_values()` | modelo_baseline | Remove features com >75% missing |
| `remove_low_cardinality_values()` | modelo_baseline | Remove features constantes ou quase-constantes |
| `split_stratified_data()` | modelo_baseline | Split estratificado por FPD (25% teste) |
| `sort_periods()` | modelo_baseline | Ordena SAFRAs e separa OOS/OOT |
| `remove_high_correlation_data()` | modelo_baseline | Remove features com correlacao >0.80 |
| `adjust_and_drop_date_cols()` | modelo_baseline | Converte datas para dias numericos |
| `convert_cep3_uf_regiao()` | modelo_baseline | Mapeia CEP3 → UF → Regiao |
| `apply_cleanings_to_df()` | modelo_baseline | Orquestra todo o pipeline |

## 2. Detalhamento

### 2.1 Limpeza de Chaves e Metadados
- Remove: NUM_CPF, SAFRA, DT_PROCESSAMENTO, _execution_id, _data_inclusao
- Mantem: todas as features comportamentais (REC_, PAG_, FAT_)

### 2.2 Filtro de Missing Values
- Threshold: 75% (features com >75% null sao removidas)
- Tratamento: NaN preenchidos com 0 para features numericas
- Justificativa: Features com muito missing perdem poder preditivo

### 2.3 Filtro de Cardinalidade
- Remove features com cardinalidade = 1 (constantes)
- Remove features com variancia zero
- Mantidas: features categoricas com 2+ valores distintos

### 2.4 Split Estratificado
- Treino: 75% (SAFRAs 202410-202501)
- OOS (Out-of-Sample): SAFRA 202502 (validacao)
- OOT (Out-of-Time): SAFRA 202503 (teste final)
- Estratificacao: por target FPD para manter proporcao

### 2.5 Filtro de Correlacao
- Threshold: 0.80 (Pearson)
- Quando par correlacionado encontrado, remove a feature com menor correlacao com o target
- Aplicado apenas no conjunto de treino

### 2.6 Encoding Geografico
- CEP3 (3 primeiros digitos do CEP) → UF → Regiao (N/NE/CO/SE/S)
- Mapeamento hardcoded com dicionario brasileiro completo
- One-hot encoding para regiao

### 2.7 Tratamento de Datas
- Converte colunas de data para dias numericos (DATEDIFF ate referencia)
- Remove colunas de data originais apos conversao

## 3. Amostragem
- Amostra de desenvolvimento: 25% do total (~975K registros)
- Justificativa: otimizar tempo de treino mantendo representatividade
- Pendente: avaliacao no dataset completo (Task HD-3.1, item 10)

---
*Hackathon PoD Academy (Claro + Oracle)*
