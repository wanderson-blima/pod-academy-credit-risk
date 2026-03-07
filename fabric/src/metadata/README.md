# Stage 2 — Tipagem e Deduplicacao

Responsavel pela transformacao de dados brutos (Bronze) em dados limpos e tipados no **Silver Lakehouse** (rawdata).

## Script

| Script | Descricao |
|--------|-----------|
| [`ajustes-tipagem-deduplicacao.py`](ajustes-tipagem-deduplicacao.py) | Tipagem dinamica + deduplicacao por PK |

## Como Funciona

### Pipeline de Transformacao

1. **Leitura de metadados** — Consulta `config.metadados_tabelas` no Bronze para obter tipos esperados por coluna
2. **Type casting dinamico** — Converte colunas para o tipo correto (int, float, varchar, date)
3. **Tratamento de datas** — Formato customizado `01MAY2024:00:00:00` convertido para date
4. **Deduplicacao** — Remove duplicatas mantendo o registro mais recente por PK + `_data_inclusao` DESC
5. **MERGE (UPSERT)** — Delta MERGE garante idempotencia: insere novos, atualiza existentes

### Tabelas Processadas

Processa dinamicamente todas as tabelas listadas em `lista_tabelas`:
- `dados_cadastrais` — Dados demograficos (UF, idade, produto)
- `telco` — Dados de telecomunicacao (plano, status, tipo)
- `dados_faturamento` — Registros de faturamento
- `pagamento` — Registros de pagamento
- `ass_recarga_cmv_nova` — Transacoes de recarga
- *(e demais tabelas da rawdata)*

## Decisoes

- **Por que MERGE e nao OVERWRITE?** MERGE preserva dados existentes e permite ingestoes incrementais. OVERWRITE recriaria a tabela inteira a cada execucao.
- **Por que deduplicar por `_data_inclusao`?** Multiplas ingestoes podem trazer o mesmo registro. Manter o mais recente garante dados atualizados.
- **Por que type casting dinamico?** Bronze usa `varchar(8000)` para tudo (by design). A Silver converte para tipos corretos baseado nos metadados.

## Destino

```
Silver Lakehouse (5f8a4808...)
└── rawdata/         ← dados tipados e deduplicados (21 tabelas)
```

---

*Veja tambem: [Arquitetura de Dados](../../docs/architecture/data-architecture.md)*
