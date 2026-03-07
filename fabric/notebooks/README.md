# Notebooks de Analise Exploratoria

Notebooks de EDA (Exploratory Data Analysis) utilizados para compreender os dados, validar hipoteses e gerar insights para o pipeline de modelagem.

## Notebooks

| Notebook | Descricao | Entregavel |
|----------|-----------|------------|
| [`estudo_publico_alvo.ipynb`](estudo_publico_alvo.ipynb) | Estudo completo do publico-alvo com 15+ visualizacoes | A |
| [`edas/eda-atrasos.ipynb`](edas/eda-atrasos.ipynb) | Analise de padroes de atraso |  |
| [`edas/eda-pagamentos.ipynb`](edas/eda-pagamentos.ipynb) | Analise de comportamento de pagamento |  |
| [`edas/eda-recarga.ipynb`](edas/eda-recarga.ipynb) | Analise de padroes de recarga |  |
| [`edas/eda_automatizada.ipynb`](edas/eda_automatizada_output_metadados.ipynb) | EDA automatizada com output de metadados |  |

## Estudo do Publico-Alvo (Entregavel A)

O notebook `estudo_publico_alvo.ipynb` cobre 9 secoes de analise:

1. **Distribuicao FPD** — Taxas de default por SAFRA e segmento
2. **Perfil Demografico** — UF/regiao, idade, produto, status
3. **Segmentacao de Risco** — FPD rate por segmento (heatmap)
4. **Comportamento Recarga** — Padroes de recarga (frequencia, valor, canal)
5. **Comportamento Pagamento** — Padroes de pagamento (atraso, faturas abertas)
6. **Comportamento Faturamento** — Ciclos, isencoes, vencimentos
7. **Migracao PRE → Controle** — Características dos migrantes
8. **Correlacao Feature-Target** — Top features correlacionadas com FPD
9. **Insights de Negocio** — Conclusoes acionáveis

**Output**: 15+ visualizacoes publication-ready + documento analitico em [`docs/analytics/estudo-publico-alvo.md`](../docs/analytics/estudo-publico-alvo.md)

---

*Os notebooks contem outputs das celulas executadas no Microsoft Fabric, incluindo graficos e tabelas geradas durante a analise.*
