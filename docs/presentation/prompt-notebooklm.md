# Prompt NotebookLM — Apresentacao Hackathon FPD

> Carregue como fontes no NotebookLM e depois cole o prompt no chat:
> 1. `visualizacoes-modelo-fpd.pdf`
> 2. `apresentacao-hackathon.md`
> 3. `README.md` do projeto

---

## PROMPT

```
<role>
Voce e um AI Presentation Architect. Cria decks executivos com estetica AI-First: ultra-clean, whitespace generoso, tipografia bold, dados como protagonistas. Seu trabalho e transformar metricas de modelos de Machine Learning em narrativas visuais que executivos entendem em 3 segundos por slide.
</role>

<task>
Crie 9 slides (10 min) para o projeto "Modelo Preditivo de Inadimplencia FPD" da Claro Telecom. Use APENAS os dados fornecidos em <data>. Zero invencao.
</task>

<context>
- Hackathon PoD Academy (Claro + Oracle), Fev 2025
- Banca: executivos de negocio + data scientists
- Google Slides 16:9. Tempo: 10 min.
</context>

<design>
TEMA: "AI-First Minimal"

Filosofia: o dado e o heroi. Nada compete com ele. Cada slide tem UM ponto. Se precisar de 2 frases para explicar, o slide falhou.

FUNDO: Branco puro (#FFFFFF). Sem excecao.
ACCENT: Preto (#111111) para titulos. Um unico accent color por slide para o KPI principal.
PALETTE:
  - Azul IA (#2563EB) — KPIs, highlights, linhas accent
  - Roxo Deep (#7C3AED) — secundario, graficos, badges tech
  - Verde Emerald (#059669) — positivo, checkmarks, ganhos
  - Slate (#334155) — corpo de texto
  - Muted (#94A3B8) — subtexto, rodapes, labels

TIPOGRAFIA:
  - Titulos: Inter Black ou Space Grotesk Bold, 32-40pt, uppercase tracking +2%
  - KPIs hero: Inter Black, 64-96pt (o numero e o slide)
  - Corpo: Inter Regular, 16-18pt
  - Labels: Inter Medium, 11pt, uppercase, letter-spacing +4%, cor Muted
  - Rodape: Inter Light, 9pt

ELEMENTOS VISUAIS:
  - Linhas: fina accent bar (2px) no topo, cor do accent do slide
  - Cards: border-radius 12px, shadow sutil (0 2px 8px rgba(0,0,0,0.06))
  - Icones: Lucide ou Phosphor, stroke-only, 24px, cor accent
  - Graficos: minimalistas, sem grid lines, labels diretos nos dados
  - Espacamento: 48px margens, 32px gap entre blocos
  - Max 3 elementos por slide. Max 25 palavras de texto corrido.
  - Sem bullet points tradicionais — usar cards, badges ou numeros grandes
  - Sem gradientes, sem sombras pesadas, sem decoracao

RODAPE (todos os slides): "PoD Academy | Claro + Oracle | 2025" em Muted, alinhado direita
</design>

<data>
=== MODELO ===
LightGBM v6 (selecionado): KS 33.97% | AUC 0.7303 | Gini 46.06 pp | PSI 0.0011
Logistic Regression L1: KS 32.77% | AUC 0.7207 | Gini 44.15 pp | PSI 0.0016
Benchmark: supera Score Bureau em +0.87 pp de KS

=== ESTABILIDADE ===
Treino (202410-412): KS 37.65%
Validacao OOS (202501): KS 35.89%
Teste OOT1 (202502): KS 34.97%
Teste OOT2 (202503): KS 33.23%
Degradacao total: 4.4 pp (controlada)
PSI todas comparacoes: < 0.002

=== DECIS ===
Decil 1: 52.73% default, Lift 2.47x
Decil 10: 5.07% default, Lift 0.24x
Top 3 decis (30% base): capturam 55.8% dos defaults
Separacao: 10x entre melhor e pior

=== SWAP ===
Top 10% negado: 90% aprovacao, 24.7% defaults evitados
Top 20% negado: 80% aprovacao, 42.1% defaults evitados
Top 30% negado: 70% aprovacao, 55.8% defaults evitados

=== FINANCEIRO ===
~450K clientes elegiveis/mes | Fatura media ~R$50
Conservador (top 10%): R$ 550K/mes
Moderado (top 20%): R$ 950K/mes
Agressivo (top 30%): R$ 1.25M/mes

=== FEATURES ===
398 iniciais -> 59 finais (85% reducao)
Pipeline: IV > 0.02 -> L1 Lasso -> Corr < 0.95 -> LGBM Top 70
Top SHAP: TARGET_SCORE_02 (29.2%), TARGET_SCORE_01 (6.8%), REC_SCORE_RISCO (4.7%)
Bureau = 36% importancia | Recarga interna = 24%
Dados internos adicionam +7 pp de KS

=== ARQUITETURA ===
Medallion: Bronze (19 tab) -> Silver (24 tab) -> Gold (2 tab, 402 col)
Fabric + PySpark + Delta Lake
Volumes: 99.9M recargas, 27.9M pagamentos, 32.7M faturamentos
Feature Store: 3.9M registros, 6 safras
Books: Recarga 90 feat | Pagamento 94 | Faturamento 114

=== PUBLICO ===
Migracao Pre-pago -> Controle
Regiao: SE > NE > S > CO > N (volume)
Maior inadimplencia: Norte e Nordeste
Maior risco etario: 18-25 anos
Maior volume etario: 25-40 anos
</data>

<slides>

SLIDE 1 — CAPA
Accent: Azul IA
- Numero hero centralizado: "33.97%" (gigante, 96pt, Azul IA)
- Label acima: "KS — PODER DE SEPARACAO DO MODELO" (11pt, uppercase, Muted)
- Titulo abaixo: "Modelo Preditivo de Inadimplencia FPD" (32pt, preto)
- Subtitulo: "Migracao Pre-pago para Controle | Claro Telecom" (16pt, Slate)
- 3 mini badges em linha: AUC 0.7303 | Lift 2.47x | PSI 0.0011
- Rodape com logos

SLIDE 2 — RESULTADO
Accent: Verde Emerald
Titulo: "O QUE ENTREGAMOS"
- 4 cards em grid 2x2, cada um com:
  - Numero hero (48pt, bold, Azul IA)
  - Label de contexto (14pt, Slate)
  Card 1: "33.97%" / "KS — supera bureau em +0.87 pp"
  Card 2: "2.47x" / "Lift — decil 1 captura 52.7% dos defaults"
  Card 3: "R$ 1.25M" / "Economia mensal estimada (cenario top 30%)"
  Card 4: "0.0011" / "PSI — estabilidade maxima entre safras"
- Frase unica abaixo (18pt, Slate, centro):
  "59 variaveis. 3.9M registros. Metade dos inadimplentes nos primeiros 10% da base."

SLIDE 3 — PROBLEMA
Accent: Roxo Deep
Titulo: "O DESAFIO"
- 3 cards horizontais com icone Lucide + texto:
  Card 1 (icone Users): "450K clientes/mes migram Pre -> Controle"
  Card 2 (icone AlertTriangle): "Alto risco de inadimplencia na 1a fatura (FPD)"
  Card 3 (icone Target): "Decisao de credito depende apenas de score bureau externo"
- Callout box (borda Roxo Deep, fundo branco):
  "Oportunidade: enriquecer com dados internos de recarga, pagamento e faturamento"

SLIDE 4 — ARQUITETURA
Accent: Roxo Deep
Titulo: "PIPELINE DE DADOS"
- Diagrama horizontal clean: 3 blocos conectados por linhas finas
  [Bronze] -> [Silver] -> [Gold]
  19 tabelas   24 tabelas   402 colunas
  staging      + 3 books     3.9M registros
- Abaixo: 3 numeros de volume em cards minimalistas
  "99.9M" recargas | "27.9M" pagamentos | "32.7M" faturamentos
- Badge pill: "Microsoft Fabric | PySpark | Delta Lake" (Roxo Deep, pill shape)

SLIDE 5 — PUBLICO
Accent: Azul IA
Titulo: "PERFIL DE RISCO"
- Layout 2 colunas:
  Esquerda: Mapa do Brasil estilizado (5 regioes com gradiente de cor por risco)
    N/NE = cor mais intensa (maior taxa FPD)
    SE = label "maior volume absoluto"
  Direita: 3 data points empilhados em cards:
    "18-25 anos" = maior taxa de inadimplencia (badge vermelho)
    "25-40 anos" = maior volume de contratos (badge azul)
    "SE + NE" = 60%+ do volume total (badge roxo)
- Insight bar (fundo Azul IA 5%, borda esquerda Azul IA 3px):
  "Norte e Nordeste: maiores taxas. Sudeste: maior volume absoluto de defaults."

SLIDE 6 — MODELO
Accent: Azul IA
Titulo: "PERFORMANCE"
- Tabela minimal (sem bordas externas, linhas finas internas):
  | Metrica | LightGBM | Log. Reg. | Bureau |
  | KS      | 33.97%   | 32.77%    | ~33.1% |
  | AUC     | 0.7303   | 0.7207    | —      |
  | Gini    | 46.06 pp | 44.15 pp  | —      |
  | PSI     | 0.0011   | 0.0016    | —      |
  (coluna LightGBM com fundo Azul IA 5%)
- Mini sparkline ao lado: KS por safra decaindo suavemente 37.65 -> 33.23
- Badge pill verde: "LightGBM selecionado"
- Callout: "Degradacao de apenas 4.4 pp em 6 meses"

SLIDE 7 — SWAP
Accent: Roxo Deep
Titulo: "RANKING E ESTABILIDADE"
- Lado esquerdo: tabela swap clean
  | Estrategia | Aprovacao | Defaults Evitados |
  | Top 10%    | 90%       | 24.7%             |
  | Top 20%    | 80%       | 42.1%             |
  | Top 30%    | 70%       | 55.8%             |
- Lado direito: comparativo visual grande
  "52.73%" (Decil 1, vermelho) vs "5.07%" (Decil 10, verde)
  Label: "10x de separacao entre pior e melhor decil"
- Mini explicacao em 2 linhas:
  "Swap-Out = modelo evita defaults que bureau aprovaria"
  "Swap-In = modelo aprova bons que bureau rejeitaria"

SLIDE 8 — IMPACTO
Accent: Verde Emerald
Titulo: "IMPACTO FINANCEIRO"
- 3 cards de cenario em linha, tamanho crescente (visual de escala):
  [Conservador]     [Moderado]        [Agressivo]
  90% aprovacao     80% aprovacao     70% aprovacao
  R$ 550K/mes       R$ 950K/mes       R$ 1.25M/mes
  (borda verde)     (borda amarela)   (borda laranja)
- Abaixo: barra horizontal de importancia SHAP (top 5):
  TARGET_SCORE_02 ████████████████████ 29.2%
  TARGET_SCORE_01 █████ 6.8%
  REC_SCORE_RISCO ████ 4.7%
  REC_TAXA_STATUS_A ██ 2.5%
  REC_QTD_LINHAS ██ 2.3%
- Callout final (bold): "Dados internos da Claro adicionam +7 pp de KS ao modelo"

SLIDE 9 — ENCERRAMENTO
Accent: Azul IA
Titulo: "PRONTO PARA PRODUCAO"
- 2 colunas:
  Esquerda — "Entregue" (icone CheckCircle verde em cada):
    Pipeline Bronze -> Silver -> Gold
    Feature Store 402 colunas
    LightGBM KS 33.97%
    Swap analysis + impacto
    Monitoramento de drift
  Direita — "Proximo" (icone ArrowRight Azul IA em cada):
    Deploy Scoring Batch
    Motor de decisao de credito
    Alertas automaticos
    Retreino trimestral
- Frase final centralizada (24pt, Azul IA, bold):
  "Modelo robusto. Estavel. Interpretavel. Pronto para reduzir a inadimplencia."

</slides>

<output>
Para cada slide retorne:

## Slide N — TITULO
### Conteudo
(texto exato que aparece no slide — copy-paste ready)
### Layout
(descricao visual: posicao, tamanhos, cores hex, alinhamento)
### Notas do Apresentador
(script de fala 60-90s, tom confiante e executivo, sem hedging)
### Transicao
(uma frase para conectar ao proximo slide)
</output>

<rules>
1. APENAS numeros de <data>. Inventar = falha critica.
2. Max 25 palavras de texto corrido por slide.
3. O numero e o slide. Texto complementa, nao compete.
4. Tom executivo: assertivo, sem "talvez", "possivelmente", "acreditamos".
5. Narrativa linear: problema -> dados -> modelo -> impacto.
6. Slides 2 e 8 sao os climaxes. Maximo impacto visual.
7. Sem bullet points. Usar cards, numeros hero, badges.
8. Jargao sempre com traducao de 3 palavras. Ex: "KS (poder de separacao)".
9. Whitespace e intencional. Se o slide parece vazio, esta certo.
10. Sem disclaimers, avisos, asteriscos ou rodapes tecnicos.
</rules>

<validate>
Antes de entregar, confirme:
- Todos os numeros existem em <data>?
- Nenhum slide tem mais de 25 palavras corridas?
- A paleta esta consistente (Azul IA / Roxo / Verde / Slate / Muted)?
- O arco narrativo funciona: problema -> dados -> modelo -> dinheiro?
- Notas cabem em 60-90s falando em ritmo normal?
- Design parece AI-First: minimal, bold, data-hero?
</validate>
```

---

## Como Usar

1. **Suba as fontes** no NotebookLM
2. **Cole o prompt** inteiro (bloco entre ```)
3. **Resultado**: conteudo slide-a-slide pronto para Google Slides

## Tecnicas Aplicadas

| Tecnica | Onde |
|---------|------|
| Role Anchoring | `<role>` — AI Presentation Architect |
| Design System Token | `<design>` — palette, tipografia, espacamento como design tokens |
| Data Grounding | `<data>` — numeros exatos, agrupados por tema |
| Slide Blueprint | `<slides>` — layout visual detalhado por slide |
| Output Schema | `<output>` — formato rigido de resposta |
| Hard Constraints | `<rules>` — 10 regras inviolaveis, sem ambiguidade |
| Self-Validation | `<validate>` — checklist de qualidade pre-entrega |
| Anti-Hallucination | Rules 1 + Data Grounding — dupla protecao |
| Narrative Arc | Rules 5-6 — arco forcado com climaxes definidos |
| Semantic Compression | Max 25 palavras — forca clareza absoluta |
