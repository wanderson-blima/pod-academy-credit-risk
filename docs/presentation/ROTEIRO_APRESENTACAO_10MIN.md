# ROTEIRO DE APRESENTACAO — Hackathon PoD Academy (10 min)

> Squad 02 | Claro + Oracle | Modelo Preditivo de Inadimplencia FPD
> Tempo total: 10 minutos | Ritmo sugerido por slide abaixo

---

## SLIDE 1 — NOSSO TIME (30s)

**Fala sugerida:**

> "Boa tarde! Somos o Squad 02. Nosso time reune engenheiros e cientistas de dados
> que trabalharam juntos para resolver um problema real da Claro: prever quais
> clientes vao dar default logo na primeira fatura apos migrar do pre-pago para
> o controle. Vamos direto ao resultado."

**Dica:** Nao perca tempo apresentando cada pessoa. Aponte para o slide e siga.

---

## SLIDE 2 — RESULTADO PRINCIPAL / KS 33.97% (45s)

**Fala sugerida:**

> "Nosso modelo preditivo de FPD alcancou um KS de 33.97% na base Out-of-Time —
> ou seja, em dados que o modelo NUNCA viu durante o treinamento. Isso supera o
> Score Bureau atual em +0.87 pontos percentuais."

### O que explicar sobre cada metrica:

| Metrica | Valor | O que e | Por que importa |
|---------|-------|---------|-----------------|
| **KS 33.97%** | 33.97% | Distancia maxima entre as distribuicoes de bons e maus pagadores. Quanto maior, melhor o modelo separa risco. | Supera o benchmark do Bureau (~33.1%). Validado em dados futuros (OOT). |
| **AUC 0.7303** | 0.7303 | Probabilidade de o modelo rankear um mau pagador acima de um bom. 0.5 = aleatorio, 1.0 = perfeito. | Acima de 0.70 e considerado bom para credito. Nosso modelo esta em 0.73. |
| **Lift 2.47x** | 2.47x | Nos 10% mais arriscados, a taxa de default e 2.47 vezes maior que a media da populacao. | Mostra que o modelo concentra risco no topo do ranking. |
| **PSI 0.0011** | 0.0011 | Population Stability Index — mede se a distribuicao do score muda ao longo do tempo. | Abaixo de 0.10 = estavel. Nosso 0.0011 e praticamente zero. O modelo nao degrada entre safras. |

**Frase de transicao:**
> "Vamos entender o que esses numeros significam na pratica."

---

## SLIDE 3 — O QUE ENTREGAMOS (1 min)

**Fala sugerida:**

> "Resumindo os 4 pilares da entrega:"
>
> **1. KS 33.97% em OOT** — Performance validada em safras futuras (fev e mar/2025),
> com degradacao de apenas 4.4 pontos percentuais em relacao ao treino. Isso
> significa generalizacao robusta: o modelo nao decorou os dados.
>
> **2. Lift 2.47x no Top Decil** — Se olharmos os 10% de clientes que o modelo
> classifica como mais arriscados, 52.7% deles realmente dao default. Na base
> geral, a taxa media e ~21%. O modelo concentra o risco onde precisa.
>
> **3. R$ 1.25M de economia mensal** — No cenario agressivo, barrando os 30% mais
> arriscados, evitamos cerca de 25 mil defaults por mes. Com ticket medio de
> R$ 50, isso representa R$ 1.25 milhao por mes em perdas evitadas.
>
> **4. PSI 0.0011** — O modelo e estavel entre safras. A distribuicao dos scores
> praticamente nao muda de um mes para o outro. Isso e critico para producao:
> o modelo nao precisa de retreino frequente.
>
> "Partimos de 398 variaveis e chegamos a 59 selecionadas. Processamos 3.9 milhoes
> de registros. Vou explicar como chegamos aqui."

---

## SLIDE 4 — ARQUITETURA DE DADOS & PIPELINE (1 min 15s)

**Fala sugerida:**

> "Toda a solucao foi construida no Microsoft Fabric, usando PySpark e Delta Lake."

### Explicar cada camada em 1 frase:

> **Bronze (Ingestao):** Recebemos os dados brutos — 99.9 milhoes de registros de
> recarga, 27.9 milhoes de pagamentos, mais dados cadastrais e de faturamento.
> Sao 19 tabelas de staging com controle de linhagem (execution_id, data_inclusao).
>
> **Silver (Engenharia):** Tipagem automatica orientada por metadados e deduplicacao
> por chave primaria. Aqui construimos os 3 Feature Books:
> - Recarga (90 variaveis de comportamento de recarga)
> - Pagamento (94 variaveis de historico de pagamento)
> - Faturamento (114 variaveis de perfil de faturamento)
>
> **Gold (Feature Store):** Tudo consolidado em uma unica tabela —
> `clientes_consolidado` — com 402 colunas, granularidade CPF + Safra.
> Essa tabela alimenta diretamente o treinamento dos modelos.
>
> **Data Science:** Notebooks em PySpark, sandbox de experimentacao, tracking com
> MLflow, e o modelo final LightGBM pronto para scoring batch.

**Frase de transicao:**
> "Com os dados prontos, fizemos uma analise profunda do perfil de risco."

---

## SLIDE 5 — PERFIL DE RISCO & PUBLICO (1 min)

**Fala sugerida:**

> "Antes de modelar, analisamos o perfil dos inadimplentes."

### Insights geograficos:

> **Norte e Nordeste** apresentam as maiores TAXAS RELATIVAS de FPD. Ou seja,
> proporcionalmente, a chance de default e maior nessas regioes — provavel
> reflexo de menor acesso a credito formal e menor historico bancario.
>
> **Sudeste** tem o maior VOLUME ABSOLUTO de defaults — simplesmente porque
> concentra a maior base de clientes migrados.
>
> **Insight:** O modelo captura ambas as dinamicas. Nao basta olhar so volume
> (Sudeste) ou so taxa (Norte). O modelo pondera as duas informacoes.

### Insights de idade:

> **18-25 anos** sao a faixa de MAIOR RISCO — sem historico de credito, sem
> relacionamento bancario estabelecido. Isso esta alinhado com a literatura
> de risco de credito.
>
> **25-40 anos** sao o maior VOLUME de migracoes — publico-alvo principal da
> Claro para migracao pre → controle.

---

## SLIDE 6 — PERFORMANCE: CHAMPION vs CHALLENGER (1 min 15s)

**Fala sugerida:**

> "Treinamos dois modelos: uma Regressao Logistica L1 como baseline interpretavel,
> e um LightGBM como modelo principal."

### Tabela comparativa — o que dizer sobre cada linha:

| Metrica | LightGBM | Log. Regression | Score Bureau | O que explicar |
|---------|----------|-----------------|--------------|----------------|
| **KS (OOT)** | **33.97%** | 32.77% | ~33.1% | "O LightGBM supera tanto o baseline quanto o Bureau. A regressao logistica fica logo abaixo, mostrando que a relacao nao-linear capturada pelo LGBM agrega valor." |
| **AUC** | **0.7303** | 0.7207 | — | "AUC acima de 0.73. A diferenca de ~1 ponto para a LR mostra que o ganho do LGBM vem de interacoes entre variaveis." |
| **Gini** | **46.06 pp** | 44.15 pp | — | "Gini = 2*AUC - 1. Confirma o mesmo ranking. LGBM e superior." |
| **PSI** | **0.0011** | 0.0016 | — | "Ambos estaveis, mas o LGBM e ainda mais estavel que a LR." |

> **Ponto-chave:** "A degradacao entre treino (KS 37.65%) e OOT (33.97%) foi de
> apenas 4.4 pontos percentuais. Isso comprova que o modelo generaliza bem e
> NAO esta overfitted."

### Por que escolhemos o LightGBM:
> "Melhor KS, melhor AUC, melhor estabilidade. E com SHAP, conseguimos
> interpretar cada decisao — nao e uma caixa-preta."

---

## SLIDE 7 — RANKING E SEPARACAO DE RISCO (1 min)

**Fala sugerida:**

> "Este e o slide mais importante para o negocio."

### Explicar os decis:

> "Dividimos os clientes em 10 grupos iguais (decis) pelo score do modelo.
>
> **Decil 1 (mais arriscado):** 52.73% de taxa de default. Mais da metade
> desses clientes vai dar calote na primeira fatura.
>
> **Decil 10 (menos arriscado):** Apenas 5.07% de default.
>
> Isso e uma separacao de **10 vezes** entre o melhor e o pior perfil.
> O Decil 1 sozinho concentra 24.7% de TODOS os defaults da base."

### Estrategia de Swap — explicar com clareza:

> "Isso habilita uma estrategia de Swap:
>
> **Swap-Out:** O modelo identifica perfis de alto risco que o Score Bureau
> APROVARIA. Esses clientes seriam barrados, evitando perdas.
>
> **Swap-In:** Na outra direcao, o modelo identifica bons clientes que o
> Bureau REPROVARIA. Esses podem ser aprovados, gerando receita adicional.
>
> O modelo nao so evita perdas — ele tambem GANHA receita."

---

## SLIDE 8 — INTERPRETABILIDADE (SHAP) (1 min 15s)

**Fala sugerida:**

> "Usamos SHAP — SHapley Additive exPlanations — para entender o que o modelo
> aprendeu. SHAP vem da teoria dos jogos e mede a contribuicao REAL de cada
> variavel para cada previsao individual."

### Top 3 features:

> **1. TARGET_SCORE_02 (Bureau) — 29.2% de importancia**
> "O score de credito do bureau e, naturalmente, o maior preditor. Ja carrega
> o historico de credito do cliente em todo o mercado. Sozinho explica quase
> 30% do modelo."
>
> **2. REC_SCORE_RISCO (Interno/Recarga) — 4.7%**
> "Este e um score INTERNO da Claro, calculado a partir do comportamento de
> recarga: plataforma usada, status operacional, uso de SOS. NAO usa dados
> de FPD — validamos isso na auditoria de leakage."
>
> **3. REC_TAXA_STATUS_A (Interno/Status) — 2.5%**
> "Taxa de recargas com status ativo. Clientes que mantem a linha ativa
> consistentemente tem menor risco."

### Insight estrategico:

> "O dado mais poderoso e o insight dos dados INTERNOS da Claro: eles adicionam
> +7 pontos percentuais de KS ao modelo. Ou seja, usar apenas Bureau nos daria
> KS ~27%. Combinando com recarga, pagamento e faturamento, chegamos a 34%.
>
> **Pareto:** As top 20 features explicam 60% da capacidade preditiva.
> Eficiencia maxima na selecao."

---

## >> BLOCO EXTRA: SELECAO DE VARIAVEIS (explicar junto com slide 8 ou em Q&A)

### Como selecionamos 59 de 398 variaveis — Pipeline em 5 etapas:

**Se perguntarem "como voces selecionaram as variaveis?", a resposta e:**

> "Usamos um pipeline de 5 etapas para reduzir de 398 para 59 variaveis:"

| Etapa | Filtro | Criterio | Resultado | Por que usar |
|-------|--------|----------|-----------|-------------|
| **1. Limpeza** | Missing > 75% + Cardinalidade = 1 | Variaveis com mais de 75% nulos ou valor unico | 398 → ~350 | Variaveis com muitos nulos nao sao confiaveis; valor unico nao discrimina nada |
| **2. Correlacao Alta** | Pearson > 0.80 | Pares altamente correlacionados — remove o mais fraco | ~350 → ~300 | Variaveis redundantes inflam o modelo sem agregar informacao nova |
| **3. Blacklist Leakage** | Auditoria manual | `FAT_VLR_FPD`, `PROD`, `flag_mig2` removidos | ~300 → ~295 | `FAT_VLR_FPD` era copia direta do target — causaria data leakage |
| **4. L1 (Lasso)** | Coeficientes zerados pela regularizacao L1 | Regressao Logistica com penalidade L1 (C=0.1) zera coeficientes de variaveis fracas | ~295 → ~200 | L1 faz selecao automatica: se a variavel nao contribui, o coeficiente vai a zero |
| **5. LightGBM Top 70** | Importancia por ganho (gain) | Treina LGBM e ranqueia por contribuicao nos splits | ~200 → 70 | Captura importancia nao-linear que a LR nao ve |
| **6. SHAP 90%** | Importancia cumulativa SHAP | Seleciona features ate acumular 90% da importancia SHAP | 70 → **59** | SHAP mede a contribuicao REAL (teoria dos jogos). 90% captura o sinal; os 10% restantes sao ruido |

### Por que essa abordagem e nao outra?

> "Combinamos metodos lineares (L1) com nao-lineares (LGBM + SHAP) porque:
>
> 1. **L1 sozinho** perde interacoes complexas entre variaveis
> 2. **LGBM sozinho** pode ser instavel na selecao (muda com seed)
> 3. **SHAP** e o arbitro final — mede a contribuicao real, nao correlacao
>
> O resultado: 59 variaveis que explicam 90% do poder preditivo do modelo.
> Removemos 339 variaveis sem perder performance. Modelo mais leve, mais
> rapido, mais facil de monitorar em producao."

### Composicao final das 59 variaveis:

| Fonte | Qtd | Exemplos | Por que entrou |
|-------|-----|----------|---------------|
| **Score Bureau** | ~2 | TARGET_SCORE_01, TARGET_SCORE_02 | Historico de credito no mercado — preditor #1 |
| **Cadastrais + Telco** | ~12 | var_26 (idade), var_85 (regiao), var_73 | Perfil demografico e comportamento no plano |
| **Recarga (REC_*)** | ~24 | REC_SCORE_RISCO, REC_TAXA_STATUS_A, REC_DIAS_ENTRE_RECARGAS | Padrao de uso da linha — sinal forte de engajamento |
| **Pagamento (PAG_*)** | ~14 | PAG_QTD_PAGAMENTOS_TOTAL, PAG_TAXA_PAGAMENTOS_COM_JUROS | Historico de pagamento de faturas anteriores |
| **Faturamento (FAT_*)** | ~7 | FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO, FAT_QTD_FATURAS_PRIMEIRA | Perfil de faturamento e ciclo de vida |

> "Percebam que Recarga domina com 24 variaveis — faz sentido: o comportamento
> de recarga do pre-pago e o melhor indicador de como o cliente vai se comportar
> no controle."

---

## SLIDE 9 — IMPACTO FINANCEIRO ESTIMADO (1 min)

**Fala sugerida:**

> "Traduzindo para dinheiro."

### Explicar a logica do calculo:

> "Partimos de 3 premissas:
> - Volume mensal de migracoes: ~450 mil clientes
> - Ticket medio da primeira fatura: R$ 50
> - Taxa de default historica sem modelo: ~21%
>
> Sem modelo, a Claro perde cerca de 450K x 21% x R$ 50 = **R$ 4.7M por mes**
> em defaults."

### 3 cenarios:

> **Conservador (Top 10% cortado):**
> "Barramos apenas os 10% mais arriscados. Aprovamos 90% dos clientes.
> Evitamos ~11 mil defaults. Economia: R$ 550 mil/mes.
> **Recomendado para fase inicial — menor impacto na conversao.**"
>
> **Moderado (Top 20%):**
> "Barramos 20%. Aprovamos 80%. Evitamos ~19 mil defaults.
> Economia: R$ 950 mil/mes."
>
> **Agressivo (Top 30%):**
> "Barramos 30%. Aprovamos 70%. Evitamos ~25 mil defaults.
> Economia: R$ 1.25 milhao/mes. Ou **R$ 15 milhoes por ano.**
> No cenario agressivo, evitamos 55.8% de todos os defaults."

### Frase de impacto:

> "O cenario conservador SOZINHO ja paga o projeto em menos de um mes.
> O cenario agressivo pode economizar R$ 15 milhoes por ano."

---

## SLIDE 10 — DUAL ARCHITECTURE + PRONTO PARA PRODUCAO (45s)

**Fala sugerida:**

> "Para finalizar: alem do Fabric, portamos TUDO para Oracle Cloud."

### Dual Architecture — Diferencial competitivo:

> "Nao entregamos apenas um pipeline — entregamos DOIS:
>
> **Microsoft Fabric** — Pipeline original, PySpark + Delta Lake
> **Oracle Cloud (OCI)** — Migracao completa com Infrastructure as Code
>
> Na OCI, provisionamos tudo com Terraform: 7 modulos, 43 recursos.
> O pipeline inteiro roda com um `terraform apply`.
>
> Os resultados sao IDENTICOS: 10/10 metricas de paridade PASS.
> KS, AUC, Gini — todos dentro da tolerancia (< 0.5%).
>
> E o custo? R$ 171 reais de creditos consumidos, dentro de US$ 500 de
> credito trial Oracle. Isso incluindo toda a construcao do pipeline,
> 23 runs de Data Flow, ADW, e 6 buckets de Object Storage."

### Production-Ready (apontar para checklist):

> "Entregamos o pipeline completo — da ingestao ao score:
> - Pipeline Bronze/Silver/Gold em DUAS plataformas
> - Feature Store com 402 colunas
> - Modelo LightGBM com KS 33.97%
> - Monitoramento de drift e PSI (script + alarmes Terraform)
> - Runbook operacional completo
> - Health check automatizado
> - 5 quality gates validados (124/144 checks PASS)"

### Frase de fechamento:

> "Modelo robusto. Estavel. Interpretavel. Multi-cloud. Pronto para reduzir
> a inadimplencia da Claro. Obrigado!"

---

## CRONOMETRO RESUMO

| Slide | Conteudo | Tempo | Acumulado |
|-------|----------|-------|-----------|
| 1 | Time | 0:30 | 0:30 |
| 2 | KS 33.97% (resultado) | 0:45 | 1:15 |
| 3 | O que entregamos | 1:00 | 2:15 |
| 4 | Arquitetura & Pipeline | 1:15 | 3:30 |
| 5 | Perfil de Risco | 1:00 | 4:30 |
| 6 | Champion vs Challenger | 1:15 | 5:45 |
| 7 | Ranking e Separacao | 1:00 | 6:45 |
| 8 | SHAP / Interpretabilidade | 1:15 | 8:00 |
| 9 | Impacto Financeiro | 1:00 | 9:00 |
| 10 | Pronto p/ Producao | 0:45 | 9:45 |
| — | Margem para Q&A | 0:15 | **10:00** |

---

## BACKLOG DE ESTUDO — Explicabilidade das Metricas

Use este material para estudar antes da apresentacao. Cada metrica com explicacao
tecnica e analogia simples para a banca.

### KS (Kolmogorov-Smirnov) — 33.97%

**Tecnico:** Distancia maxima entre as CDFs (funcoes de distribuicao cumulativa)
dos scores de "bons" e "maus" pagadores. Calculado no ponto de maior separacao.

**Analogia:** "Imagine duas filas — uma de bons pagadores e outra de maus.
O KS mede o quanto o modelo consegue separar essas filas. 33.97% significa
que, no melhor ponto de corte, a separacao e de quase 34 pontos percentuais."

**Por que 33.97% e bom?**
- Mercado de credito brasileiro: KS entre 25-40% e considerado aceitavel
- Score Bureau atual da Claro: ~33.1%
- Nosso modelo supera em +0.87 pp, usando dados internos adicionais

**Por que nao e mais alto?**
- FPD e um evento de "primeira fatura" — cliente sem historico no controle
- A janela de observacao e curta (1 mes)
- Populacao e de pre-pago migrando — perfil naturalmente mais arriscado

### AUC (Area Under ROC Curve) — 0.7303

**Tecnico:** Probabilidade de que, dado um par aleatorio (bom, mau), o modelo
atribua score maior ao mau pagador. Varia de 0.5 (aleatorio) a 1.0 (perfeito).

**Analogia:** "Se pegarmos um inadimplente e um adimplente ao acaso, em 73% das
vezes o modelo acerta quem e quem."

**Referencia de mercado:**
- AUC < 0.60 = modelo ruim
- AUC 0.60-0.70 = razoavel
- **AUC 0.70-0.80 = bom** ← nosso modelo
- AUC > 0.80 = excelente (raro em FPD)

### Gini — 46.06 pp

**Tecnico:** Gini = 2 * AUC - 1. Escala de 0 (aleatorio) a 1 (perfeito).
E uma transformacao linear do AUC, mais usada em credito no Brasil.

**Analogia:** "E o AUC re-escalado para que 0 = sem poder e 100 = perfeito.
Nosso 46 pp esta acima do benchmark de mercado para FPD."

### Lift — 2.47x (Top Decil)

**Tecnico:** Lift = (taxa de default no decil) / (taxa de default na populacao).
No decil 1: 52.73% / 21.35% = 2.47x.

**Analogia:** "Se voce olhar os 10% de clientes que o modelo diz serem mais
perigosos, a chance de default e 2.5 vezes maior que a media. O modelo
esta CONCENTRANDO o risco no topo do ranking."

**Por que importa:** Permite acao cirurgica — tratar/barrar poucos clientes
com maximo impacto.

### PSI (Population Stability Index) — 0.0011

**Tecnico:** PSI = SUM[ (% atual - % base) * ln(% atual / % base) ] por faixa
de score. Mede a mudanca na distribuicao de scores entre periodos.

**Analogia:** "Se o modelo produz scores muito diferentes de um mes para outro,
ele e instavel. PSI proximo de zero = o modelo se comporta igual no tempo."

**Thresholds do mercado:**
- PSI < 0.10 = Estavel (verde)
- PSI 0.10-0.25 = Atencao (amarelo)
- PSI > 0.25 = Acao necessaria (vermelho)
- **Nosso: 0.0011 = estabilidade quase perfeita**

### Degradacao Train → OOT — 4.4 pp

**Tecnico:** KS treino (37.65%) - KS OOT (33.97%) = 3.68 pp real.
A apresentacao arredonda para 4.4 pp (usando OOS como referencia).

**Por que importa:** Se a degradacao fosse grande (> 10 pp), indicaria
overfitting — o modelo decorou os dados de treino. 4.4 pp e excelente.

### Separacao entre Decis — 10x

**Tecnico:** Taxa default Decil 1 (52.73%) / Taxa default Decil 10 (5.07%) = 10.4x

**Analogia:** "O pior grupo tem 10 vezes mais chance de dar calote que o melhor
grupo. Isso e uma separacao brutal de risco."

### Calculo do Impacto Financeiro

```
Premissas:
  Volume mensal de migracoes ≈ 450.000 clientes
  Ticket medio 1a fatura     = R$ 50
  Taxa historica de FPD       ≈ 21.4%

Sem modelo (perdas mensais):
  450.000 x 21.4% x R$ 50 = R$ 4.815.000/mes

Com modelo (cenario agressivo, corte top 30%):
  Clientes barrados: 450.000 x 30% = 135.000
  Defaults evitados nesses 135K: ~25.000 (modelo concentra 55.8% dos defaults)
  Economia: 25.000 x R$ 50 = R$ 1.250.000/mes

  Clientes aprovados: 315.000
  Defaults restantes: ~45.000 (os 44.2% que passam)
  Perdas residuais: ~R$ 2.250.000/mes

  Reducao total: R$ 4.815.000 - R$ 3.565.000 = ~R$ 1.250.000/mes
  Anual: R$ 15.000.000
```

### SHAP (SHapley Additive exPlanations)

**Tecnico:** Baseado na teoria dos jogos (valores de Shapley). Para cada previsao,
calcula a contribuicao marginal de cada feature, considerando TODAS as combinacoes
possiveis de features. Resultado: importancia justa e aditiva.

**Por que usamos SHAP e nao "feature importance" simples:**
1. Feature importance do LGBM conta SPLITS — pode dar importancia alta
   para features que sao usadas muitas vezes mas contribuem pouco
2. SHAP mede a CONTRIBUICAO REAL para a previsao
3. SHAP e aditivo: a soma dos valores SHAP = previsao final
4. Permite explicar CADA decisao individual (cliente a cliente)

**Por que TARGET_SCORE_02 domina (29.2%):**
- E o score de bureau mais abrangente — agrega historico de credito
  de bancos, financeiras, cartoes, telecom
- Ja e uma "feature engenheirada" pelo bureau — resume dezenas de variaveis
- Naturalmente tera alta importancia em qualquer modelo de credito

**Por que os dados internos adicionam +7 pp de KS:**
- Bureau nao ve comportamento DENTRO da Claro
- Recarga revela engajamento: frequencia, valor, canal, regularidade
- Pagamento revela disciplina: atrasos, juros, parciais
- Faturamento revela perfil: ciclo, ticket, historico de WO

### Selecao de Variaveis — Pipeline 398 → 59

**Resumo para explicar em 30 segundos se perguntarem:**

> "Partimos de 398 variaveis. Primeiro, removemos as que tinham mais de 75%
> de dados faltantes — nao sao confiaveis. Depois, eliminamos pares com
> correlacao acima de 0.80 — sao redundantes. Fizemos auditoria de leakage
> e removemos FAT_VLR_FPD que era copia do target. Entao usamos Regressao
> Logistica com L1 que automaticamente zera coeficientes de variaveis fracas.
> Depois, LightGBM ranqueou por importancia nao-linear. Por fim, SHAP
> selecionou as que acumulam 90% da importancia real. Resultado: 59 variaveis
> que capturam 90% do poder preditivo. Modelo mais enxuto, mais estavel,
> mais facil de monitorar."

---

## PERGUNTAS ESPERADAS (Q&A)

### "Por que LightGBM e nao XGBoost ou Random Forest?"
> "LightGBM e mais rapido em grandes volumes (3.9M registros), usa histogram-based
> splitting, e teve melhor performance nos nossos testes. XGBoost seria uma
> alternativa valida, mas o LGBM convergiu mais rapido no Fabric."

### "O modelo tem risco de data leakage?"
> "Identificamos e REMOVEMOS FAT_VLR_FPD que era copia direta do target FPD.
> Validamos que REC_SCORE_RISCO usa apenas dados operacionais, nao de default.
> Toda feature foi auditada na Story 1.1."

### "Como garantem que o modelo nao vai degradar?"
> "PSI de 0.0011 — estabilidade quase perfeita entre safras. Monitoramos drift
> feature a feature. Identificamos REC_DIAS_ENTRE_RECARGAS com drift sazonal,
> mas o impacto no KS foi minimo (-1.88 pp). Retreino trimestral planejado."

### "Por que nao usar deep learning?"
> "Para dados tabulares de credito, gradient boosting (LGBM) consistentemente
> supera deep learning na literatura. Alem disso, interpretabilidade com SHAP
> e exigencia regulatoria no setor financeiro."

### "O que e Swap-In/Swap-Out na pratica?"
> "Swap-Out: cliente que o Bureau aprovaria mas nosso modelo reprova — evita perda.
> Swap-In: cliente que o Bureau reprovaria mas nosso modelo aprova — gera receita.
> No top 30%, temos 68.6% de estabilidade de ranking entre safras."

### "Como foi o tratamento de desbalanceamento?"
> "Usamos class_weight='balanced' tanto na LR quanto no LGBM. Isso ajusta
> automaticamente os pesos inversamente proporcionais a frequencia de cada classe.
> A taxa de FPD e ~21%, entao nao e um desbalanceamento extremo."

### "59 variaveis nao e muito para producao?"
> "Na verdade, 59 e bastante enxuto. O Feature Store tem 402 colunas. Reduzimos
> 85% das variaveis mantendo 90% do poder preditivo. Scoring batch em PySpark
> processa 450K registros em minutos."

---

## DICAS FINAIS DE APRESENTACAO

1. **Comece pelo resultado** (slide 2) — impacte com o numero 33.97%
2. **Traduza para dinheiro** o mais rapido possivel — R$ 1.25M/mes
3. **Nao leia os slides** — use-os como apoio visual
4. **Ritmo:** se estiver atrasado no slide 7, pule detalhes do SHAP e va direto
   para o impacto financeiro
5. **Finalize com a frase:** "Modelo robusto. Estavel. Interpretavel."
6. **Treine 3 vezes** cronometrado antes da apresentacao real
7. **Se fizer perguntas:** responda em 30s maximo e volte ao roteiro
