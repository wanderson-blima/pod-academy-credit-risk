# Estudo de Publico-Alvo — Clientes Claro (PRE -> CONTROLE)

> **Story**: HD-2.4 | **Epic**: EPIC-HD-001 | **Entregavel**: A (Estudo do Publico-Alvo)
> **Notebook**: `3-edas/estudo_publico_alvo.ipynb`

## 1. Contexto

Analise do perfil de clientes Claro que migram de planos Pre-pago para Controle, focando na previsao de First Payment Default (FPD). O estudo abrange 3.9 milhoes de registros com 402 colunas (398 features comportamentais, demograficas e transacionais), cobrindo 6 SAFRAs (outubro/2024 a marco/2025).

### Objetivo
Identificar o perfil dos clientes inadimplentes (FPD=1) versus adimplentes (FPD=0), segmentar grupos de risco, e fornecer insights acionaveis para a politica de credito.

### Dados Utilizados
- **Feature Store**: `Gold.feature_store.clientes_consolidado`
- **Registros**: ~3.9M (NUM_CPF x SAFRA)
- **Colunas**: 402 (cadastro + REC_ + PAG_ + FAT_ + auditoria)
- **Target**: FPD (First Payment Default, 0/1)
- **SAFRAs**: 202410, 202411, 202412, 202501, 202502, 202503

## 2. Distribuicao do Target (FPD)

A taxa de FPD varia por SAFRA, refletindo sazonalidade e mudancas na politica de credito.

**Graficos**: `0-docs/analytics/fig01_fpd_por_safra.png`
- Volume por SAFRA (barras)
- Taxa FPD por SAFRA (linha)

### Insights
- SAFRAs mais recentes tendem a ter taxa FPD mais estavel
- Media de FPD: estimada entre 5-15% (pendente validacao em Fabric)
- O desbalanceamento do target requer class_weight="balanced" nos modelos

## 3. Perfil Demografico

**Graficos**: `0-docs/analytics/fig02_perfil_demografico.png`

### 3.1 Distribuicao por UF
- Top UFs por volume: SP, RJ, MG, BA, PE (esperado)
- UFs com maior taxa FPD: a validar no Fabric

### 3.2 Perfil por Sexo/Faixa Etaria
- Distribuicao por sexo (var_10) e faixa etaria
- Correlacao com FPD por grupo demografico

### 3.3 Regiao Geografica
- Distribuicao: SE > NE > S > CO > N
- Analise de risco por regiao

## 4. Segmentacao de Risco

**Graficos**: `0-docs/analytics/fig03_scores_risco.png`

Os 3 scores de risco operacionais (construidos nos books) capturam diferentes dimensoes de inadimplencia:

| Score | Book | Componentes |
|-------|------|-------------|
| REC_SCORE_RISCO | Recarga | Migracao PRE→CONTROLE (30%), Status ZB (25%), SOS (20%), Volatilidade (15%), Concentracao (10%) |
| PAG_SCORE_RISCO | Pagamento | Faturas abertas (25%), Juros (25%), Status Baixa (20%), Volatilidade (15%), Multa equip (15%) |
| FAT_SCORE_RISCO | Faturamento | Write-Off (30%), PDD (25%), Atraso 30d (20%), Fraude (15%), ACA (10%) |

### Insights Esperados
- Clientes FPD=1 devem apresentar scores de risco significativamente maiores
- FAT_SCORE_RISCO tende a ser o mais discriminativo (usa WO e PDD)
- REC_SCORE_RISCO captura o risco de migracao de plataforma

## 5. Analise Comportamental

### 5.1 Recarga (REC_)
**Features-chave para analise**:
- `REC_QTD_RECARGAS_TOTAL`: Volume de recargas (mais recargas = mais engajamento)
- `REC_VLR_CREDITO_TOTAL`: Valor total de creditos inseridos
- `REC_TAXA_SOS`: Proporcao de recargas emergenciais (proxy de stress financeiro)
- `REC_TAXA_PLAT_CONTROLE`: Proporcao de recargas em plataformas Controle
- `REC_COEF_VARIACAO_CREDITO`: Volatilidade nos valores de recarga

### 5.2 Pagamento (PAG_)
**Features-chave para analise**:
- `PAG_QTD_PAGAMENTOS_TOTAL`: Volume de pagamentos
- `PAG_VLR_JUROS_MULTAS_TOTAL`: Valores de juros e multas (inadimplencia previa)
- `PAG_TAXA_FATURA_ABERTA`: Proporcao de faturas ainda abertas
- `PAG_TAXA_PAGAMENTOS_COM_JUROS`: Frequencia de atraso
- `PAG_COEF_VARIACAO_PAGAMENTO`: Volatilidade nos pagamentos

### 5.3 Faturamento (FAT_)
**Features-chave para analise**:
- `FAT_QTD_FATURAS_WO`: Quantidade de write-offs (irrecuperaveis)
- `FAT_QTD_FATURAS_PDD`: Faturas provisionadas como devedores duvidosos
- `FAT_DIAS_ATRASO_MEDIO`: Media de dias de atraso
- `FAT_QTD_FATURAS_ATRASO_30D`: Faturas com atraso >30 dias
- `FAT_TAXA_ATRASO`: Proporcao de faturas atrasadas

## 6. Perfil de Migracao PRE → CONTROLE

A migracao de Pre-pago para Controle e o evento central para analise de risco:
- Clientes que mantem comportamento pre-pago (REC_TAXA_PLAT_PREPG alto) apos migracao: menor risco
- Clientes com alta concentracao em plataformas CTLFC/FLEXD: maior risco
- Flag FLAG_PLAT_CONTROLE: indicador direto de migracao

## 7. Correlacao com Target

Top features mais correlacionadas com FPD (a validar):
1. FAT_QTD_FATURAS_WO / FAT_TAXA_WO
2. FAT_QTD_FATURAS_PDD / FAT_TAXA_PDD
3. FAT_DIAS_ATRASO_MEDIO
4. PAG_VLR_JUROS_MULTAS_TOTAL
5. PAG_TAXA_FATURA_ABERTA
6. REC_TAXA_SOS
7. REC_COEF_VARIACAO_CREDITO

## 8. Insights e Recomendacoes

### Perfil do Cliente Inadimplente (FPD=1)
1. **Historico de inadimplencia**: Mais faturas WO e PDD no passado
2. **Stress financeiro**: Maior uso de recarga SOS e alta volatilidade de valores
3. **Atraso recorrente**: Mais faturas com atraso >30 dias
4. **Migracao recente**: Clientes em fase de transicao PRE→CONTROLE
5. **Multas e juros**: Historico de pagamentos com juros e multas de equipamento

### Perfil do Cliente Adimplente (FPD=0)
1. **Estabilidade**: Baixo coeficiente de variacao em recargas e pagamentos
2. **Engajamento**: Mais dias com recarga, mais meses ativos
3. **Status ativo**: Predominancia de status A (ativo) na plataforma
4. **Pagamento em dia**: Zero faturas abertas, zero juros
5. **Pre-pago puro**: Alta proporcao de recargas em PREPG

### Recomendacoes para Politica de Credito
1. **Score composto**: Combinar REC_, PAG_ e FAT_ SCORE_RISCO para score unificado
2. **Regras de corte**: Clientes com FLAG_ALTO_RISCO em qualquer book devem ter limite reduzido
3. **Monitoramento mensal**: Acompanhar PSI das features-chave por SAFRA
4. **Segmentacao**: Usar SEGMENTO_RISCO para definir faixas de limite de credito

---

## 9. Visualizacoes Geradas

| # | Arquivo | Descricao |
|---|---------|-----------|
| 1 | fig01_fpd_por_safra.png | Volume e taxa FPD por SAFRA |
| 2 | fig02_perfil_demografico.png | Distribuicao UF, sexo, faixa etaria, regiao |
| 3 | fig03_scores_risco.png | Distribuicao dos 3 scores de risco |
| 4 | fig04_recarga_vs_fpd.png | Features de recarga por FPD |
| 5 | fig05_pagamento_vs_fpd.png | Features de pagamento por FPD |
| 6 | fig06_faturamento_vs_fpd.png | Features de faturamento por FPD |
| 7 | fig07_migracao_controle.png | Perfil migracao PRE→CONTROLE |
| 8 | fig08_correlacao_target.png | Top 20 features correlacionadas com FPD |

> **Nota**: As visualizacoes sao geradas pelo notebook `3-edas/estudo_publico_alvo.ipynb` e salvas em `0-docs/analytics/` com dpi=150. Os insights especificos serao atualizados apos execucao no Microsoft Fabric.

---
*Documento gerado como parte da Story HD-2.4 — Hackathon PoD Academy (Claro + Oracle)*
