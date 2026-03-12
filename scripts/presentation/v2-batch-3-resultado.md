# =============================================================================
# V2 BATCH 3 — RESULTADO: O QUE O MODELO ENTREGA (Slides 9-12)
# Hackathon PoD Academy — Claro + Oracle
# =============================================================================
# Narrativa: Agora que o publico entende a jornada tecnica, mostrar o que o
# modelo entrega na pratica: scores, cenarios financeiros, drill-down, dashboard.
# =============================================================================

prompt: |
  Crie 4 slides de apresentacao executiva (16:9, 1920x1080) para o Hackathon PoD Academy (Claro + Oracle).
  Estes sao os slides 10 a 13 de 17. Terceiro bloco: O que o modelo entrega.
  Mantenha consistencia visual com os 8 slides anteriores.

  ## DESIGN SYSTEM (siga rigorosamente)

  **Fundo**: Branco puro (#FFFFFF). SEM fundos escuros.
  **Cards**: Fundo #F8F9FA, border-radius 12px, borda 1px cyan rgba(0,240,255,0.3), shadow sutil, padding 24px.
  **Cards KPI Hero**: Fundo branco, borda 2px #00F0FF, glow 0 0 20px rgba(0,240,255,0.3), padding 32px.
  **Cores de acento**: Cyan #00F0FF (primario), Green #00FF88 (positivo), Yellow #FFD600 (alerta), Red #FF3366 (critico).
  **Texto**: Titulos #1A1A2E (36-42pt Bold), Corpo #4A4A6A (16-18pt), Labels #8A8AAA (12-14pt uppercase).
  **Numeros Hero**: 64-80pt ExtraBold #1A1A2E.
  **Tipografia**: Inter ou Montserrat.
  **Decoracao**: Linhas finas de circuito impresso nos cantos (cyan 30% opacity), grid de pontos sutil no fundo.
  **Header**: Barra com logo Claro (esquerda) + Oracle (direita), borda inferior cyan.
  **Footer**: "Hackathon PoD Academy — Marco 2026" (esquerda) + "Slide N/17" (direita), 10pt #8A8AAA.
  **Tabelas**: Header #1A1A2E fundo com texto branco, linhas alternadas branco/#F8F9FA, borda cyan sutil.
  **Margens**: 80px em todos os lados.

  ---

  ## SLIDE 10 — SCORE DISTRIBUTION + FAIXAS DE RISCO

  **Layout**: Grafico histograma (topo, 60%) + tabela de faixas (embaixo, 40%).

  **Titulo do slide**: "Distribuicao de Score — 3.9M Clientes" (36pt Bold)

  **Grafico Principal (area superior, 60% do slide)**:
  - Histograma vertical mostrando a distribuicao dos scores
  - Eixo X: Score (0 a 1000, bins de 50 ou 100)
  - Eixo Y: Numero de clientes
  - Cores das barras por faixa de risco:
    - 0-299: Vermelho (#FF3366)
    - 300-499: Amarelo (#FFD600)
    - 500-699: Cyan (#00F0FF)
    - 700-1000: Verde (#00FF88)
  - Linha vertical tracejada no cutoff 700, label "CUTOFF 700 (Conservador)"
  - Estatisticas no canto: Mean=538, Median=546, Std=214, Min=23, Max=982

  **Tabela de Faixas (embaixo do grafico)**:
  | Faixa | Range | Clientes | % Total | FPD Rate |
  |-------|-------|----------|---------|----------|
  | CRITICO | 0-299 | 669.521 | 17.2% | 59.2% |
  | ALTO | 300-499 | 1.011.756 | 25.9% | 34.8% |
  | MEDIO | 500-699 | 1.108.849 | 28.4% | 17.5% |
  | BAIXO | 700-1000 | 1.110.252 | 28.5% | 6.9% |

  Formatacao: cada linha com cor de fundo sutil da faixa correspondente.
  Coluna FPD Rate com cor contextual (vermelho→amarelo→cyan→verde).

  Nota: A tabela usa risk_distribution_all (3.9M) e FPD rates de confusion_matrix_results (labelados).

  **Footnote**: "Fonte: scoring_summary.json (3.900.378) + confusion_matrix_results.json (FPD rates dos 2.696.621 labelados)"

  ---

  ## SLIDE 11 — IMPACTO FINANCEIRO: 3 CENARIOS

  **Layout**: 3 cards de cenario lado a lado + barra de decisao embaixo.

  **Titulo do slide**: "Impacto Financeiro — 3 Cenarios de Cutoff" (36pt Bold)
  **Subtitulo**: "Trade-off entre protecao contra inadimplencia e volume de aprovacao" (16pt, #4A4A6A)

  **3 Cards de Cenario** (lado a lado, largura igual):

  Card Esquerdo — "AGRESSIVO (Volume)":
  - Header do card: borda 2px #00FF88, glow verde
  - Badge: "UNICO LIQ. POSITIVO" em verde
  - Cutoff: "Score 300" (20pt Bold)
  - 4 mini-KPIs:
    - Aprovados: "93.3%"
    - FPD Aprovados: "18.4%"
    - Economia bruta: "R$ 5.5M"
    - Receita perdida: "R$ 3.8M"
  - Hero: Economia liquida "+R$ 1.7M" (28pt Bold, #00FF88)

  Card Central — "EQUILIBRADO":
  - Header do card: borda 1px cyan (#00F0FF)
  - Badge: "BREAKEVEN" em cyan
  - Cutoff: "Score 400" (20pt Bold)
  - 4 mini-KPIs:
    - Aprovados: "83.5%"
    - FPD Aprovados: "15.6%"
    - Economia bruta: "R$ 10.7M"
    - Receita perdida: "R$ 11.2M"
  - Hero: Economia liquida "~R$ 0" (28pt Bold, #FFD600)

  Card Direito — "CONSERVADOR (Risco)":
  - Header do card: borda 1px #FFD600
  - Badge: "MIN. INADIMPLENCIA" em amarelo
  - Cutoff: "Score 700" (20pt Bold)
  - 4 mini-KPIs:
    - Aprovados: "36.3%"
    - FPD Aprovados: "7.2%"
    - Economia bruta: "R$ 22.9M"
    - Receita perdida: "R$ 56.9M"
  - Hero: Economia liquida "-R$ 34.0M" (28pt Bold, #FF3366)

  **Card de decisao (embaixo, largura total)**:
  Card com borda cyan sutil, fundo #F8F9FA:
  - "Decisao de negocio: o cutoff ideal depende do LGD real, CAC, ARPU e estrategia comercial da Claro." (14pt, #4A4A6A)
  - "O modelo entrega a ferramenta de decisao — a politica de credito e da area de negocios." (14pt Bold, #1A1A2E)

  **Footnote**: "Fonte: swap_summary.json | LGD proxy = R$44,89 (mediana VAL_FAT_ABERTO) | Base: 2.696.621 clientes labelados"

  ---

  ## SLIDE 12 — CONFUSION MATRIX BUSINESS

  **Layout**: Matriz 2x2 visual (centro) + cards financeiros embaixo.

  **Titulo do slide**: "Matriz de Confusao — Impacto em Reais" (36pt Bold)
  **Subtitulo**: "Cutoff 700 (cenario conservador) | 2.696.621 clientes labelados" (18pt, #4A4A6A)

  **Matriz 2x2 (centro do slide)**:
  Grid 2x2 com cards grandes, visual estilo confusion matrix:

  ┌─────────────────────────────────────────────┐
  │           PREDITO: APROVADO │ PREDITO: REJEITADO │
  ├─────────────────────────────────────────────┤
  │ REAL:    │ TP (Bom→Aprovado)│ FN (Bom→Rejeitado) │
  │ BOM      │ 856.141          │ 1.266.850           │
  │          │ Verde #00FF88    │ Cinza #8A8AAA       │
  │          │ "Receita gerada" │ "Receita perdida"   │
  │          │ R$ 38.4M         │ R$ 56.9M            │
  ├──────────┼──────────────────┼─────────────────────┤
  │ REAL:    │ FP (Mau→Aprovado)│ TN (Mau→Rejeitado)  │
  │ MAU      │ 63.133           │ 510.497             │
  │          │ Vermelho #FF3366 │ Verde escuro         │
  │          │ "Perda residual" │ "Perda bruta evitada"│
  │          │ R$ 2.83M         │ R$ 22.9M (bruto)    │
  └─────────────────────────────────────────────┘

  Cada quadrante e um card com:
  - Titulo (TP/FP/TN/FN) em 12pt uppercase
  - Quantidade de clientes em 28pt Bold
  - Valor financeiro em 24pt Bold (cor contextual)
  - Descricao em 14pt

  **3 KPI Cards (embaixo da matriz, inline)**:
  - Card 1: "PERDA RESIDUAL: R$ 2.83M" (vermelho) — "Maus que passaram"
  - Card 2: "PERDA BRUTA EVITADA: R$ 22.9M" (verde) — "Maus barrados"
  - Card 3: "RECEITA PERDIDA: R$ 56.9M" (laranja) — "Bons rejeitados"

  **Footnote**: "Fonte: confusion_matrix_results.json (cutoff 700) | LGD proxy R$44,89 | Receita proxy = mediana VAL_FAT_LIQUIDO"

  ---

  ## SLIDE 13 — APEX DASHBOARD

  **Layout**: Cards de paginas (centro) + callouts laterais.

  **Titulo do slide**: "Dashboard de Monitoramento — Oracle APEX" (36pt Bold)
  **Subtitulo**: "Self-service para a area de negocios — Always Free" (16pt, #4A4A6A)

  **4 Cards (2x2 grid) representando as paginas do dashboard**:

  Card 1: "Score Distribution"
  - Icone: bar chart
  - "Histograma interativo por faixa de risco" (13pt)
  - Cor de acento: cyan

  Card 2: "Model Metrics"
  - Icone: table
  - "KS, AUC, Gini — todos os modelos" (13pt)
  - Cor de acento: verde

  Card 3: "Drift Monitor"
  - Icone: trend line
  - "PSI por SAFRA + feature drift" (13pt)
  - Cor de acento: amarelo

  Card 4: "Financial Impact"
  - Icone: dollar sign
  - "Simulacao de cenarios por cutoff" (13pt)
  - Cor de acento: vermelho

  **Callouts (ao redor dos cards, 4 badges)**:
  - "8 ORDS Endpoints" (REST API nativa)
  - "Always Free" (badge verde — custo zero)
  - "Real-time" (dados atualizados via sync)
  - "Self-service" (executivos acessam sem TI)

  **Footnote**: "Oracle APEX on ADW Always Free | 8 REST endpoints | Acessivel via browser"

slides:
  - number: 10
    title: "Score Distribution + Faixas"
    data_sources:
      - "scoring_summary.json: risk_distribution_all, score_stats_all"
      - "confusion_matrix_results.json: risk_band_contingency (FPD rates)"
  - number: 11
    title: "Impacto Financeiro — 3 Cenarios"
    data_sources:
      - "swap_summary.json: cutoff_analysis (300, 400, 700)"
      - "business-value-analysis.md: economia bruta vs liquida por cenario"
  - number: 12
    title: "Confusion Matrix Business"
    data_sources:
      - "confusion_matrix_results.json: cutoff 700 — TP=856141, FP=63133, TN=510497, FN=1266850"
      - "Financial: loss_bad=R$2.83M, avoided_loss_gross=R$22.9M, lost_revenue=R$56.9M"
  - number: 13
    title: "APEX Dashboard"
    data_sources:
      - "APEX URL, 8 ORDS endpoints, Always Free ADW"
