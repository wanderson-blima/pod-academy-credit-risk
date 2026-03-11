# Dashboard de Custos OCI - Plataforma de Risco de Credito

## Estimativas de Custo Mensal

| Cenario | Custo Mensal (USD) | Detalhes |
|---------|-------------------|----------|
| Tudo parado | ~$6 | Apenas Object Storage (4 buckets, ~50 GB) |
| 1 execucao/mes (8h) | ~$22 | Orchestrator 8h + Data Flow + ADW 8h |
| Desenvolvimento semanal (8h/semana) | ~$45 | + Notebook ativo durante horario comercial |
| Producao 24/7 | ~$165 | Todos os recursos ligados continuamente |

---

## Detalhamento por Servico

### Object Storage (Sempre ativo)

| Item | Custo |
|------|-------|
| Primeiros 10 GB/bucket (Always Free) | $0 |
| Armazenamento adicional (~50 GB total) | ~$1.20/mes |
| Requests (PUT, GET) | ~$0.03/10K requests |
| **Total estimado** | **~$6/mes** |

### Compute - Orchestrator (E3.Flex)

| Item | Custo |
|------|-------|
| Shape E3.Flex (2 OCPUs, 32 GB) | ~$0.04/OCPU/hora |
| 8h/mes (1 execucao) | ~$0.64 |
| 32h/mes (semanal) | ~$2.56 |
| 24/7 (730h) | ~$58.40 |

### Compute - Notebook (E3.Flex)

| Item | Custo |
|------|-------|
| Shape E3.Flex (2-4 OCPUs, 32-64 GB) | ~$0.04/OCPU/hora |
| Parado | $0 |
| 32h/mes (desenvolvimento semanal) | ~$5.12 |
| 24/7 (730h) | ~$116.80 |

### ADW (Always Free)

| Item | Custo |
|------|-------|
| Always Free Tier | $0 |
| APEX incluso | $0 |
| **Total** | **$0** |

### Data Catalog (Always Free)

| Item | Custo |
|------|-------|
| Always Free Tier | $0 |
| **Total** | **$0** |

---

## Comandos para Parar/Iniciar Recursos

### Orchestrator VM

```bash
# Parar (soft stop)
oci compute instance action \
  --instance-id <INSTANCE_OCID> \
  --action SOFTSTOP \
  --auth instance_principal

# Iniciar
oci compute instance action \
  --instance-id <INSTANCE_OCID> \
  --action START \
  --auth instance_principal
```

### ADW (Autonomous Database)

```bash
# Parar
oci db autonomous-database stop \
  --autonomous-database-id ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq

# Iniciar
oci db autonomous-database start \
  --autonomous-database-id ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq
```

**Nota**: ADW Always Free reinicia automaticamente apos 7 dias parado.

### Data Science Notebook

```bash
# Desativar
oci data-science notebook-session deactivate \
  --notebook-session-id <NOTEBOOK_SESSION_OCID>

# Ativar
oci data-science notebook-session activate \
  --notebook-session-id <NOTEBOOK_SESSION_OCID>
```

---

## Servicos que Podem Ser Parados

| Servico | Pode Parar? | Impacto ao Parar | Economia |
|---------|-------------|-------------------|----------|
| Orchestrator VM | Sim | Airflow indisponivel, sem execucoes agendadas | ~$58/mes (se 24/7) |
| Notebook VM | Sim | Sem desenvolvimento, sem treinamento | ~$117/mes (se 24/7) |
| ADW | Sim (Always Free) | Dashboard APEX indisponivel | $0 (Always Free) |
| Object Storage | Nao parar | Perda de dados | N/A |
| Data Catalog | Nao parar | Always Free, sem custo | $0 |

---

## Estrategia de Otimizacao Recomendada

### Cenario Economico (Hackathon/Demo)

1. Manter Object Storage sempre ativo (custo minimo)
2. Ligar Orchestrator apenas para execucoes do pipeline
3. Ligar Notebook apenas para desenvolvimento/treinamento
4. ADW Always Free - manter ligado (sem custo)
5. **Custo estimado: ~$6-22/mes**

### Cenario de Desenvolvimento

1. Orchestrator ligado durante horario comercial (8h/dia, 5 dias/semana)
2. Notebook ligado conforme demanda
3. **Custo estimado: ~$45/mes**

### Cenario de Producao

1. Orchestrator 24/7 para agendamentos do Airflow
2. Notebook sob demanda (treinamento mensal)
3. **Custo estimado: ~$165/mes**

---

## Limitacoes do Trial

| Limitacao | Detalhe |
|-----------|---------|
| ARM A1 (Ampere) | OUT_OF_HOST_CAPACITY em sa-saopaulo-1 - nao disponivel |
| E3/E4 Flex | Maximo 4 OCPUs por instancia (trial) |
| Data Science | Limite separado de 24 OCPUs |
| Availability Domain | Unico: TjOZ:SA-SAOPAULO-1-AD-1 |
| Credito Trial | $500 USD |
| Object Storage Always Free | 10 GB por bucket, 20 GB total |
| ADW Always Free | 1 OCPU, 20 GB storage |

---

## Referencias de Precos OCI

- [OCI Compute Pricing](https://www.oracle.com/cloud/compute/pricing/)
- [OCI Object Storage Pricing](https://www.oracle.com/cloud/storage/pricing/)
- [OCI ADW Pricing](https://www.oracle.com/autonomous-database/pricing/)
- [OCI Always Free Resources](https://www.oracle.com/cloud/free/)
- [OCI Cost Estimator](https://www.oracle.com/cloud/costestimator.html)

> **Nota**: Precos baseados na regiao sa-saopaulo-1 (Sao Paulo). Valores podem variar. Consulte a calculadora oficial da OCI para estimativas atualizadas.
