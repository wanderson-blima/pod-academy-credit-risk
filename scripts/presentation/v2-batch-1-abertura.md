# =============================================================================
# V2 BATCH 1 — ABERTURA: HOOK + CONTEXTO + KPIs (Slides 1-4)
# Hackathon PoD Academy — Claro + Oracle
# =============================================================================
# Narrativa: Apresentar o projeto, dar contexto de negocio, mostrar resultado
# em numeros, e revelar a riqueza dos dados antes de entrar na tecnica.
# =============================================================================

prompt: |
  Crie 4 slides de apresentacao executiva (16:9, 1920x1080) para o Hackathon PoD Academy (Claro + Oracle).
  Estes sao os slides 1 a 4 de 17. Primeiro bloco: Abertura.

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

  ## SLIDE 1 — TITLE SLIDE

  **Layout**: Centrado, impactante, minimalista.

  **Elementos**:
  - Centro superior: Titulo principal em 2 linhas
    - Linha 1: "Plataforma de Credit Risk" (42pt Bold, #1A1A2E)
    - Linha 2: "IA-First" (64pt ExtraBold, com gradiente cyan→green ou cor #00F0FF)
  - Abaixo do titulo: Subtitulo "Predicao de First Payment Default para Telecom" (18pt, #4A4A6A)
  - Meio: Linha divisoria fina cyan (#00F0FF, 30% opacity, 400px largura)
  - Abaixo da linha: "Hackathon PoD Academy" (24pt Bold, #1A1A2E)
  - Logo bar: Claro + Oracle lado a lado, centralizados
  - Footer: "Marco 2026" centralizado
  - Decoracao: Linhas de circuito nos 4 cantos do slide, mais elaboradas que nos demais slides

  **Mood**: Futurista, confiante, corporate. Primeiro impacto visual forte.

  ---

  ## SLIDE 2 — CONTEXTO DO PROJETO

  **Layout**: Lado esquerdo (55%) texto + lado direito (45%) visual do fluxo do cliente.

  **Titulo do slide**: "O Projeto" (36pt Bold, #1A1A2E)

  **Lado Esquerdo — Contexto de Negocio**:

  Card principal (fundo #F8F9FA, padding 32px):
  - Titulo do card: "Migracao Pre-pago → Controle" (20pt Bold, #1A1A2E)
  - Texto (16pt, #4A4A6A, line-height 1.6):
    "A Claro busca expandir sua base de planos controle, migrando clientes pre-pagos.
    O desafio: identificar quais clientes tem menor risco de inadimplencia apos
    a migracao — o chamado First Payment Default (FPD)."
  - Linha divisoria fina cyan
  - Subtexto (14pt, #4A4A6A):
    "Este projeto constroi um motor de score de credito end-to-end: da ingestao
    dos dados brutos ate um score por cliente, com monitoramento e dashboard
    para a area de negocios."

  **Lado Direito — Fluxo Visual do Cliente**:
  Diagrama vertical simples (3 etapas conectadas por setas):

  Etapa 1 (card, borda cinza):
  - Icone: smartphone
  - "Cliente Pre-pago" (16pt Bold)
  - "Historico de recargas, pagamentos, faturamento" (12pt, #8A8AAA)

  Seta ↓ com label "Migracao" (cyan)

  Etapa 2 (card, borda cyan, destaque):
  - Icone: credit card
  - "Plano Controle" (16pt Bold)
  - "Primeiro boleto emitido" (12pt, #8A8AAA)

  Seta ↓ com label "30-90 dias" (cyan)

  Etapa 3 — bifurcacao em 2 cards lado a lado:
  - Card esquerdo (borda verde): "Adimplente" — "Pagou" — icone checkmark (#00FF88)
  - Card direito (borda vermelha): "FPD" — "Nao pagou" — icone X (#FF3366)

  **Card de contexto (embaixo, largura total)**:
  - "FPD baseline: ~21% da base | 6 SAFRAs analisadas (Out/2024 a Mar/2025) | 3.9M registros" (14pt, #4A4A6A)

  **Footnote**: "First Payment Default = cliente que nao paga o primeiro boleto apos migracao de plano"

  ---

  ## SLIDE 3 — MODELO CAMPEAO: RESULTADOS

  **Layout**: Card hero do champion (topo, 35%) + 3 cards de metricas (centro, 35%) + barra de contexto (embaixo, 30%).

  **Titulo do slide**: "Modelo Campeao — Top-3 Average Ensemble" (36pt Bold, #1A1A2E)
  **Subtitulo**: "LightGBM + XGBoost + CatBoost (media simples, pesos iguais)" (16pt, #4A4A6A)

  **Card Hero Champion (topo, centralizado, largura ~70%)**:
  Card KPI Hero com borda 2px verde (#00FF88) e glow verde:
  - Label: "CHAMPION ENSEMBLE" (12pt uppercase, #8A8AAA)
  - 3 Hero Numbers inline:
    - "KS = 0.350" (48pt ExtraBold, #1A1A2E) — label "Out-of-Time" (11pt)
    - "AUC = 0.737" (48pt ExtraBold, #1A1A2E) — label "Out-of-Time" (11pt)
    - "Gini = 47.4%" (48pt ExtraBold, #1A1A2E) — label "Out-of-Time" (11pt)
  - Badge: "QG-05 PASSED" (pill verde, checkmark) + "PSI = 0.0008" (pill cyan)
  - Nota (12pt, #8A8AAA): "OOT = SAFRAs 202502-202503 (dados futuros, nao vistos no treino)"

  **3 Cards de Metricas (centro, grid 3 colunas)**:

  Card 1 — "Por que Ensemble?":
  - Icone: 3 circulos sobrepostos
  - "5 modelos treinados" (16pt Bold)
  - "3 selecionados para ensemble" (14pt, #4A4A6A)
  - Mini-lista (12pt):
    - "LightGBM: KS 0.349, GAP 12.0%"
    - "XGBoost: KS 0.349, GAP 14.5%"
    - "CatBoost: KS 0.348, GAP 7.0%"
  - Insight (11pt Bold): "Media reduz variancia sem perder discriminacao"

  Card 2 — "Estabilidade":
  - Icone: linha estavel / heartbeat
  - "PSI Score: ALL GREEN" (16pt Bold, #00FF88)
  - Mini-lista (12pt):
    - "6 SAFRAs testadas"
    - "PSI max: 0.004 (muito abaixo de 0.10)"
    - "Score medio: 538 (estavel)"
  - Badge: "WARNING" (#FFD600) — "13 features com drift moderado"
  - Insight (11pt Bold): "Score estavel, monitorar features com PSI 0.10-0.18"

  Card 3 — "Impacto Financeiro":
  - Icone: cifrao com setas
  - "3 cenarios de cutoff" (16pt Bold)
  - Mini-tabela (12pt):
    | Cenario | Cutoff | Econ. Liq. |
    |---------|--------|------------|
    | Agressivo | 300 | +R$ 1.7M |
    | Equilibrado | 400 | ~R$ 0 |
    | Conservador | 700 | -R$ 34M |
  - Insight (11pt Bold): "Cutoff e decisao de negocio — modelo entrega a ferramenta"

  **Barra de Contexto (embaixo, largura total)**:
  Card fino horizontal, fundo #F8F9FA, 4 dados inline:
  - "3.9M clientes scorados" (14pt Bold) — "6 SAFRAs" (11pt, #8A8AAA)
  - "110 features selecionadas" (14pt Bold) — "de 402 candidatas" (11pt, #8A8AAA)
  - "< R$ 170/mes" (14pt Bold) — "custo infra OCI" (11pt, #8A8AAA)
  - "~6h43 pipeline" (14pt Bold) — "dados brutos → score" (11pt, #8A8AAA)

  **Footnote**: "Fonte: Run 20260311_015100 | Ensemble Top-3 Average | OOT: SAFRAs 202502-202503 | LGD proxy R$44,89"

  ---

  ## SLIDE 4 — OS DADOS

  **Layout**: Centro — visual de convergencia de 5 fontes para 1 feature store.

  **Titulo do slide**: "Os Dados — 5 Fontes, 402 Features" (36pt Bold, #1A1A2E)
  **Subtitulo**: "Granularidade: CPF + SAFRA (mes de referencia)" (16pt, #4A4A6A)

  **Diagrama de Convergencia (area central, 70%)**:
  5 cards-fonte na esquerda convergindo (com setas) para 1 card-destino na direita.

  Card fonte 1 (topo):
  - Icone: pessoa
  - "CADASTRO" (14pt Bold)
  - "UF, sexo, faixa etaria, tipo plano" (11pt, #8A8AAA)
  - Badge: "~33 vars" (pill, fundo #F8F9FA)

  Card fonte 2:
  - Icone: antena/sinal
  - "TELCO" (14pt Bold)
  - "Tempo contrato, linhas, tipo servico" (11pt, #8A8AAA)
  - Badge: "~66 vars"

  Card fonte 3:
  - Icone: moeda/recarga
  - "RECARGA (REC_*)" (14pt Bold, #00FF88)
  - "Valores, frequencia, tendencia 3M/6M" (11pt, #8A8AAA)
  - Badge: "102 vars"

  Card fonte 4:
  - Icone: calendario/boleto
  - "PAGAMENTO (PAG_*)" (14pt Bold, #FFD600)
  - "Atrasos, % pago, historico 3M/6M" (11pt, #8A8AAA)
  - Badge: "154 vars"

  Card fonte 5:
  - Icone: fatura
  - "FATURAMENTO (FAT_*)" (14pt Bold, #00F0FF)
  - "Valores, concentracao, tendencia" (11pt, #8A8AAA)
  - Badge: "108 vars"

  Setas convergindo → (linhas cyan, 1px)

  Card destino (direita, maior, borda 2px #FFD600 dourado, glow):
  - "FEATURE STORE" (20pt Bold, #1A1A2E)
  - "Gold.clientes_consolidado" (12pt mono, #8A8AAA)
  - Hero: "402 features" (36pt Bold, #1A1A2E)
  - "3.9M registros × 6 SAFRAs" (14pt, #4A4A6A)
  - "Particionado por SAFRA" (11pt, #8A8AAA)

  **Mini-cards embaixo (3 inline)**:
  - "LEFT JOIN on (CPF, SAFRA)" (12pt mono) — padrao de join
  - "Target: FPD (binary)" (12pt) — variavel alvo
  - "Out/2024 a Mar/2025" (12pt) — periodo

  **Footnote**: "Fonte: Microsoft Fabric → OCI Object Storage | Medallion Architecture (Bronze → Silver → Gold)"

slides:
  - number: 1
    title: "Title Slide"
    data_sources: []
  - number: 2
    title: "Contexto do Projeto"
    data_sources:
      - "Projeto: predicao de FPD para migracao pre-pago → controle"
      - "FPD baseline ~21.3%, 6 SAFRAs, 3.9M registros"
  - number: 3
    title: "Modelo Campeao — Resultados"
    data_sources:
      - "ensemble_results.json: ks_oot=0.35005, auc_oot=0.73677, gini_oot=47.35, psi=0.000754"
      - "training_results_20260311_015100.json: 5 models, GAP analysis, feature count=110"
      - "monitoring_report.json: score_psi all GREEN, 13 features YELLOW"
      - "business-value-analysis.md: 3 cenarios cutoff (300/400/700)"
  - number: 4
    title: "Os Dados"
    data_sources:
      - "Feature store: 402 features, 5 fontes (CADASTRO ~33, TELCO ~66, REC 92, PAG 96, FAT 116)"
      - "3.9M registros, 6 SAFRAs (202410-202503), granularidade CPF+SAFRA"
