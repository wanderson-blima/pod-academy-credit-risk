# Dicionario de Dados - Features Selecionadas

## Visao Geral

| Metrica | Valor |
|---------|-------|
| **Total de features selecionadas** | 110 |
| **Funil de selecao** | 357 -> 185 -> 162 -> 114 -> 110 -> 110 |
| **Variavel alvo** | FPD (First Payment Default) |
| **Safras de treino** | 202410, 202411, 202412, 202501 |
| **Safras OOT** | 202502, 202503 |

**Fonte**: `artifacts/selected_features.json`

---

## Convencoes de Nomenclatura

| Prefixo/Sufixo | Significado | Exemplo |
|-----------------|-------------|---------|
| `QTD_` | Contagem de eventos | QTD_FATURAS = numero de faturas |
| `VLR_` | Valor monetario (R$) | VLR_CREDITO_TOTAL = valor total em creditos |
| `TAXA_` | Proporcao/taxa (0 a 1) | TAXA_ATRASO = proporcao de atrasos |
| `DIAS_` | Metrica temporal (dias) | DIAS_ATRASO_MEDIO = media de dias em atraso |
| `COEF_VARIACAO` | Coeficiente de variacao (std/media) | COEF_VARIACAO_REAL = dispersao relativa |
| `INDICE_CONCENTRACAO` | Indice tipo Herfindahl | Mede concentracao em poucas categorias |
| `AMPLITUDE` | Amplitude (max - min) | Faixa de variacao do valor |
| `RATIO_` | Razao entre dois valores | RATIO_BONUS_CREDITO = bonus/credito |
| `SHARE_` | Participacao percentual | SHARE_CARTAO_ONLINE = % cartao online |
| `FREQ_` | Frequencia | FREQ_RECARGA_DIARIA = recargas por dia |
| `SCORE_` | Score calculado | SCORE_RISCO = score de risco derivado |
| `_STDDEV` | Desvio padrao | VLR_REAL_STDDEV |
| `_MEDIO` / `_MEDIA` | Media | VLR_CREDITO_MEDIO |
| `_MIN` / `_MAX` | Minimo / Maximo | DIAS_ATRASO_MIN, DIAS_ATRASO_MAX |
| `_TOTAL` | Soma total | VLR_CREDITO_TOTAL |

---

## Grupo FAT_ (Faturamento / Billing)

Features derivadas do book de faturamento. Descrevem o historico de faturas do cliente.

| Feature | Tipo | Descricao | IV | PSI |
|---------|------|-----------|-----|-----|
| FAT_DIAS_DESDE_ULTIMA_FAT | Temporal | Dias desde a ultima fatura emitida | 0.0879 | 0.1672 |
| FAT_QTD_FATURAS | Contagem | Numero total de faturas no periodo | 0.1463 | 0.1622 |
| FAT_INDICE_CONCENTRACAO_FAT | Indice | Concentracao (Herfindahl) de faturas por tipo | 0.1430 | 0.1419 |
| FAT_TAXA_ATRASO | Taxa | Proporcao de faturas em atraso | 0.1452 | 0.1401 |
| FAT_QTD_FATURAS_SEM_PDD | Contagem | Faturas sem provisao para devedores duvidosos | 0.1187 | 0.1259 |
| FAT_INDICE_CONCENTRACAO_PLATAFORMA | Indice | Concentracao de faturas por plataforma | 0.1179 | 0.1211 |
| FAT_QTD_FAT_AUTOC | Contagem | Faturas da plataforma autocuidado | 0.0545 | 0.0926 |
| FAT_VLR_MEDIO_WO | Monetario | Valor medio de write-off (baixa contabil) | 0.0305 | 0.0911 |
| FAT_QTD_FAT_POSPG | Contagem | Faturas pos-pago | 0.0532 | 0.0730 |
| FAT_VLR_FAT_AUTOC | Monetario | Valor total de faturas autocuidado | 0.0650 | 0.0508 |
| FAT_VLR_MEDIO_PDD | Monetario | Valor medio de PDD (provisao) | 0.0245 | 0.0478 |
| FAT_DIAS_ATRASO_MEDIO | Temporal | Media de dias em atraso | 0.0479 | 0.0441 |
| FAT_VLR_FAT_ABERTO_TOTAL | Monetario | Valor total de faturas em aberto | 0.1299 | 0.0378 |
| FAT_VLR_FAT_SEM_PDD | Monetario | Valor de faturas sem provisao PDD | 0.1032 | 0.0351 |
| FAT_DIAS_ATRASO_MIN | Temporal | Menor periodo de atraso registrado (dias) | 0.0576 | 0.0348 |
| FAT_VLR_FAT_LIQ_JM_MC_TOTAL | Monetario | Valor liquido total (juros + multa + MC) | 0.1314 | 0.0346 |
| FAT_DIAS_MAX_CRIACAO_VENCIMENTO | Temporal | Maximo de dias entre criacao e vencimento | 0.0482 | 0.0298 |
| FAT_QTD_FATURAS_PRIMEIRA | Contagem | Faturas no primeiro ciclo | 0.2519 | 0.0251 |
| FAT_DIAS_DESDE_ATIVACAO_CONTA | Temporal | Dias desde a ativacao da conta | 0.3428 | 0.0228 |
| FAT_VLR_PRIMEIRA_FAT | Monetario | Valor da primeira fatura | 0.2957 | 0.0216 |
| FAT_DIAS_ATRASO_MAX | Temporal | Maior periodo de atraso registrado (dias) | 0.3279 | 0.0173 |
| FAT_TAXA_MULTA_JUROS | Taxa | Proporcao de juros e multas sobre faturamento | 0.0331 | 0.0172 |
| FAT_VLR_FAT_CREDITO_TOTAL | Monetario | Valor total de faturas de credito | 0.0397 | 0.0171 |
| FAT_QTD_FATURAS_NAO_ISENTAS | Contagem | Faturas nao isentas de cobranca | 0.2410 | 0.0148 |
| FAT_AMPLITUDE_RELATIVA_FAT | Indice | Amplitude relativa do faturamento (max-min)/media | 0.2010 | 0.0081 |
| FAT_VLR_FAT_BRUTO_STDDEV | Dispersao | Desvio padrao do valor bruto de faturas | 0.1338 | 0.0079 |
| FAT_QTD_FAT_SEM_PLATAFORMA | Contagem | Faturas sem plataforma identificada | 0.0201 | 0.0076 |
| FAT_QTD_FATURAS_ATRASADAS | Contagem | Total de faturas com atraso | 0.1060 | 0.0063 |
| FAT_VLR_FAT_CREDITO_MEDIO | Monetario | Valor medio de faturas de credito | 0.0962 | 0.0063 |
| FAT_VLR_MEDIO_PRIMEIRA_FAT | Monetario | Valor medio da primeira fatura | 0.0761 | 0.0057 |
| FAT_DIAS_MIN_CRIACAO_VENCIMENTO | Temporal | Minimo de dias entre criacao e vencimento | 0.0214 | 0.0057 |
| FAT_VLR_FAT_ABERTO_LIQ_MEDIO | Monetario | Valor liquido medio de faturas em aberto | 0.0380 | 0.0049 |
| FAT_VLR_FAT_LIQUIDO_MEDIO | Monetario | Valor liquido medio de todas as faturas | 0.0347 | 0.0034 |
| FAT_VLR_FAT_ABERTO_MEDIO | Monetario | Valor medio de faturas em aberto | 0.0362 | 0.0031 |
| FAT_TAXA_PRIMEIRA_FAT | Taxa | Proporcao da primeira fatura sobre o total | 0.3677 | 0.0016 |
| FAT_VLR_FAT_ABERTO_MAX | Monetario | Valor maximo de uma fatura em aberto | 0.0560 | 0.0008 |

**Total: 36 features FAT_**

---

## Grupo PAG_ (Pagamento / Payment)

Features derivadas do book de pagamento. Descrevem o comportamento de pagamento do cliente.

| Feature | Tipo | Descricao | IV | PSI |
|---------|------|-----------|-----|-----|
| PAG_QTD_STATUS_R | Contagem | Pagamentos com status R (recusado/rejeitado) | 0.0221 | 0.1403 |
| PAG_VLR_ALOCACAO_PYM | Monetario | Valor alocado em pagamentos PYM | 0.1825 | 0.1377 |
| PAG_TAXA_STATUS_R | Taxa | Proporcao de pagamentos recusados | 0.0611 | 0.1351 |
| PAG_VLR_ORIGINAL_PAGAMENTO_TOTAL | Monetario | Valor original total de pagamentos | 0.1503 | 0.1293 |
| PAG_VLR_BAIXA_ATIVIDADE_TOTAL | Monetario | Valor total de baixas por atividade | 0.1504 | 0.1290 |
| PAG_DIAS_DESDE_ULTIMA_FATURA | Temporal | Dias desde a ultima fatura de pagamento | 0.1026 | 0.0742 |
| PAG_TAXA_FORMA_PB | Taxa | Proporcao de pagamentos via PB (boleto bancario) | 0.0233 | 0.0682 |
| PAG_TAXA_FORMA_CA | Taxa | Proporcao de pagamentos via cartao | 0.0435 | 0.0597 |
| PAG_VLR_STATUS_R | Monetario | Valor de pagamentos recusados | 0.0354 | 0.0569 |
| PAG_VLR_TICKET_MEDIO_CONTRATO | Monetario | Ticket medio por contrato | 0.1808 | 0.0499 |
| PAG_VLR_TIPO_O | Monetario | Valor de pagamentos tipo O (outros) | 0.0324 | 0.0442 |
| PAG_VLR_STATUS_C | Monetario | Valor de pagamentos com status C (confirmado) | 0.0246 | 0.0131 |
| PAG_COEF_VARIACAO_PAGAMENTO | Dispersao | Coeficiente de variacao dos valores de pagamento | 0.0743 | 0.0082 |
| PAG_VLR_PAGAMENTO_FATURA_STDDEV | Dispersao | Desvio padrao do valor de pagamento por fatura | 0.0555 | 0.0069 |
| PAG_TAXA_PAGAMENTOS_COM_JUROS | Taxa | Proporcao de pagamentos com juros | 0.0407 | 0.0052 |
| PAG_QTD_FORMA_DD | Contagem | Pagamentos via debito direto | 0.0528 | 0.0043 |
| PAG_QTD_FORMA_PA | Contagem | Pagamentos via PA (pagamento automatico) | 0.0222 | 0.0038 |
| PAG_VLR_FORMA_PA | Monetario | Valor de pagamentos automaticos | 0.0583 | 0.0034 |
| PAG_TAXA_FORMA_PA | Taxa | Proporcao de pagamentos automaticos | 0.0629 | 0.0022 |
| PAG_VLR_PAGAMENTO_FATURA_MEDIO | Monetario | Valor medio de pagamento por fatura | 0.0372 | 0.0022 |
| PAG_VLR_TIPO_D | Monetario | Valor de pagamentos tipo D (debito) | 0.0563 | 0.0018 |
| PAG_TAXA_FORMA_DD | Taxa | Proporcao de pagamentos via debito direto | 0.0424 | 0.0010 |
| PAG_VLR_PAGAMENTO_CREDITO_MAX | Monetario | Valor maximo de pagamento de credito | 0.0390 | 0.0009 |
| PAG_VLR_JUROS_MULTAS_MEDIO | Monetario | Valor medio de juros e multas | 0.0318 | 0.0006 |
| PAG_TAXA_JUROS_SOBRE_PAGAMENTO | Taxa | Proporcao de juros sobre o valor do pagamento | 0.0552 | 0.0005 |

**Total: 25 features PAG_**

---

## Grupo REC_ (Recarga / Recharge)

Features derivadas do book de recarga. Descrevem o comportamento de recarga prepaga do cliente.

| Feature | Tipo | Descricao | IV | PSI |
|---------|------|-----------|-----|-----|
| REC_QTD_DIAS_RECARGA | Contagem | Dias distintos com recarga no periodo | 0.0395 | 0.0938 |
| REC_QTD_PLAT_AUTOC | Contagem | Recargas via plataforma autocuidado | 0.1135 | 0.0600 |
| REC_QTD_RECARGAS_TOTAL | Contagem | Total de recargas realizadas | 0.0259 | 0.0540 |
| REC_VLR_REAL_STDDEV | Dispersao | Desvio padrao do valor real de recargas | 0.0699 | 0.0468 |
| REC_RATIO_BONUS_CREDITO | Razao | Razao bonus/credito | 0.0391 | 0.0418 |
| REC_INDICE_CONCENTRACAO_CREDITO | Indice | Concentracao de creditos de recarga | 0.0374 | 0.0367 |
| REC_QTD_STATUS_ZB1 | Contagem | Recargas com status ZB1 | 0.0688 | 0.0327 |
| REC_QTD_CARTAO_ONLINE | Contagem | Recargas via cartao online | 0.0292 | 0.0272 |
| REC_VLR_CREDITO_TOTAL | Monetario | Valor total de creditos de recarga | 0.0389 | 0.0271 |
| REC_COEF_VARIACAO_REAL | Dispersao | Coeficiente de variacao do valor real | 0.0754 | 0.0251 |
| REC_QTD_INSTITUICOES | Contagem | Instituicoes distintas utilizadas para recarga | 0.0233 | 0.0161 |
| REC_VLR_BONUS_TOTAL | Monetario | Valor total de bonus recebidos | 0.0876 | 0.0155 |
| REC_QTD_PLANOS | Contagem | Planos distintos do cliente | 0.0207 | 0.0151 |
| REC_TAXA_STATUS_ZB1 | Taxa | Proporcao de recargas com status ZB1 | 0.0848 | 0.0108 |
| REC_TAXA_STATUS_A | Taxa | Proporcao de recargas com status A (ativa) | 0.0859 | 0.0107 |
| REC_QTD_CLIENTES_DW | Contagem | Clientes distintos no data warehouse | 0.0512 | 0.0099 |
| REC_DIAS_DESDE_ULTIMA_RECARGA | Temporal | Dias desde a ultima recarga | 0.0351 | 0.0099 |
| REC_QTD_TIPOS_RECARGA | Contagem | Tipos distintos de recarga | 0.0618 | 0.0094 |
| REC_TAXA_SOS | Taxa | Proporcao de recargas SOS (emergencia) | 0.1385 | 0.0049 |
| REC_TAXA_CARTAO_PROMO | Taxa | Proporcao de recargas via cartao promocional | 0.0910 | 0.0040 |
| REC_FREQ_RECARGA_DIARIA | Frequencia | Frequencia media diaria de recargas | 0.0293 | 0.0034 |
| REC_QTD_SOS | Contagem | Total de recargas SOS (emergencia) | 0.0804 | 0.0033 |
| REC_QTD_CARTAO_CHIPPRE | Contagem | Recargas via chip pre-pago | 0.0240 | 0.0031 |
| REC_SHARE_CARTAO_ONLINE | Participacao | Participacao % de cartao online nas recargas | 0.1508 | 0.0026 |
| REC_VLR_CREDITO_STDDEV | Dispersao | Desvio padrao do valor de credito | 0.0523 | 0.0026 |
| REC_VLR_CREDITO_MIN | Monetario | Valor minimo de credito de recarga | 0.1345 | 0.0020 |
| REC_TAXA_CARTAO_ONLINE | Taxa | Proporcao de recargas via cartao online | 0.0812 | 0.0013 |
| REC_SCORE_RISCO | Score | Score de risco derivado do comportamento de recarga | 0.1571 | 0.0011 |
| REC_TAXA_PLAT_PREPG | Taxa | Proporcao de recargas na plataforma pre-pago | 0.0703 | 0.0009 |
| REC_TAXA_PLAT_AUTOC | Taxa | Proporcao de recargas na plataforma autocuidado | 0.0804 | 0.0006 |
| REC_COEF_VARIACAO_CREDITO | Dispersao | Coeficiente de variacao do valor de credito | 0.0673 | 0.0054 |

**Total: 31 features REC_**

---

## Grupo var_ (Variaveis Codificadas / Bureau)

Variaveis originarias de bureau de credito ou fontes externas. Nomes codificados por confidencialidade.

| Feature | IV | PSI | Observacao |
|---------|-----|-----|-----------|
| var_02 | 0.0997 | 0.0002 | Variavel de bureau, alta estabilidade |
| var_05 | 0.0814 | 0.00004 | Variavel de bureau, muito estavel |
| var_07 | 0.0541 | 0.00005 | Variavel de bureau, muito estavel |
| var_08 | 0.0790 | 0.00009 | Variavel de bureau, muito estavel |
| var_16 | 0.0309 | 0.0053 | Variavel de bureau |
| var_32 | 0.0835 | 0.0005 | Variavel de bureau |
| var_34 | 0.1100 | 0.0005 | Variavel de bureau |
| var_35 | 0.1499 | 0.0008 | Variavel de bureau, alto IV |
| var_41 | 0.1354 | 0.0002 | Variavel de bureau, alto IV |
| var_50 | 0.0489 | 0.0001 | Variavel de bureau |
| var_61 | 0.0653 | 0.00006 | Variavel de bureau, muito estavel |
| var_62 | 0.0915 | 0.0003 | Variavel de bureau |
| var_66 | 0.0225 | N/A | Variavel de bureau |
| var_67 | 0.0237 | 0.0019 | Variavel de bureau |
| var_71 | 0.0246 | 0.0010 | Variavel de bureau |
| var_72 | 0.0479 | 0.0011 | Variavel de bureau |
| var_73 | 0.0709 | 0.0058 | Variavel de bureau |
| var_82 | 0.0201 | 0.0016 | Variavel de bureau, IV no limiar |
| var_89 | 0.0427 | 0.0022 | Variavel de bureau |

**Total: 19 features var_**

**Nota**: As variaveis `var_` possuem os menores PSI do conjunto (alta estabilidade temporal), indicando que sao provenientes de fontes externas menos sujeitas a sazonalidade.

---

## Grupo TARGET_ (Scores Alvo)

Variaveis de score de bureau utilizadas como features preditivas (nao confundir com a variavel alvo FPD).

| Feature | Tipo | Descricao | IV | PSI |
|---------|------|-----------|-----|-----|
| TARGET_SCORE_01 | Score | Score de bureau primario | 0.4271 | 0.0059 |
| TARGET_SCORE_02 | Score | Score de bureau secundario | 0.6377 | 0.0032 |

**Total: 2 features TARGET_**

**Nota**: Apesar do prefixo "TARGET_", estas variaveis sao usadas como features preditivas no modelo. A variavel alvo real e `FPD` (First Payment Default, binaria 0/1).

---

## Variavel Alvo: FPD

| Atributo | Valor |
|----------|-------|
| **Nome** | FPD (First Payment Default) |
| **Tipo** | Binario (0/1/NULL) |
| **Definicao** | Indica se o cliente inadimpliu na primeira fatura |
| **0** | Pagou a primeira fatura em dia |
| **1** | Nao pagou a primeira fatura (default) |
| **NULL** | Sem informacao (safras mais recentes sem maturacao) |

---

## Resumo por Grupo

| Grupo | Prefixo | Quantidade | IV Medio | PSI Medio | Fonte |
|-------|---------|------------|----------|-----------|-------|
| Faturamento | FAT_ | 36 | 0.1119 | 0.0362 | book_faturamento |
| Pagamento | PAG_ | 25 | 0.0614 | 0.0355 | book_pagamento |
| Recarga | REC_ | 31 | 0.0694 | 0.0191 | book_recarga_cmv |
| Bureau | var_ | 19 | 0.0672 | 0.0013 | score_bureau_movel |
| Target Scores | TARGET_ | 2 | 0.5324 | 0.0046 | score_bureau_movel |
| **Total** | | **110** | | | |

---

## Interpretacao dos Indicadores

### Information Value (IV)

| Faixa IV | Poder Preditivo |
|----------|-----------------|
| < 0.02 | Sem poder preditivo (excluido no Stage 1) |
| 0.02 - 0.10 | Fraco |
| 0.10 - 0.30 | Medio |
| 0.30 - 0.50 | Forte |
| > 0.50 | Muito forte (suspeito de leakage) |

### Population Stability Index (PSI)

| Faixa PSI | Estabilidade | Alerta |
|-----------|-------------|--------|
| < 0.10 | Estavel | GREEN |
| 0.10 - 0.25 | Atencao moderada | YELLOW |
| > 0.25 | Instavel (excluido no Stage 4) | RED |
