# ARCHITECTURE.md — Leads de Origem

> Mapa vivo do sistema. Atualizar ao fim de cada sessão que mudar código ou decisões.

---

## 1. Visão geral

Leads de Origem é uma pipeline de dados Python que extrai contatos do Klaviyo, determina a origem real de cada lead via UTM, e armazena o resultado estruturado no Supabase para análise.

**Fluxo resumido:**
```
Klaviyo API
  └── Contatos criados em [data_inicio, data_fim]
        └── Para cada contato:
              1. Verificar UTM na propriedade de contato
              2. Se não encontrado: buscar evento mais antigo com UTM
              3. Mapear UTMs → Origem (1 das 15 categorias)
              4. Gravar no Supabase
```

**Estado atual (Fase 1 — Fundação):**
Nenhum código implementado ainda. Estrutura de pastas e documentação criadas. Próximo passo: criar schema do Supabase e `KlaviyoClient`.

---

## 2. Módulos do sistema

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `src/config.py` | Carregar e expor variáveis de ambiente | python-dotenv |
| `src/klaviyo/client.py` | Chamadas à API do Klaviyo com retry e paginação | httpx, config |
| `src/klaviyo/models.py` | Tipos de dados: Contato, Evento | — |
| `src/attribution/rules.py` | Tabela de mapeamento UTM → Origem (15 categorias) | — |
| `src/attribution/mapper.py` | Lógica de atribuição: propriedade → evento → sem_utm | rules, klaviyo/models |
| `src/supabase/client.py` | Upsert de leads e consultas na base | supabase-py, config |
| `src/pipeline/extract.py` | Orquestra a extração: busca contatos, atribui origem, grava | klaviyo/client, attribution/mapper, supabase/client |
| `scripts/run_extraction.py` | Entry point: inicializa e roda o pipeline | pipeline/extract |

---

## 3. Modelo de dados (Supabase)

### Tabela: `leads`

```sql
CREATE TABLE leads (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  klaviyo_id          TEXT NOT NULL UNIQUE,
  email               TEXT,
  criado_em           TIMESTAMPTZ NOT NULL,
  origem              TEXT NOT NULL,
  utm_source          TEXT,
  utm_medium          TEXT,
  utm_campaign        TEXT,
  utm_content         TEXT,
  utm_term            TEXT,
  metodo_atribuicao   TEXT NOT NULL CHECK (metodo_atribuicao IN ('propriedade_contato', 'evento_mais_antigo', 'sem_utm')),
  processado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_leads_criado_em ON leads (criado_em);
CREATE INDEX idx_leads_origem ON leads (origem);
```

**Chave de unicidade:** `klaviyo_id` — garante idempotência na extração.

**Valores de `origem`:**
`Google Institucional`, `Instagram/Facebook`, `Google`, `Email Campanha`, `Direto`, `Social`, `Orgânico`, `Unassigned`, `Auto Referral`, `Email Fluxo`, `WhatsApp`, `Comercial`, `WhatsApp Campanha`, `WhatsApp Fluxo`, `Influencer`

---

## 4. Fluxos de dados

### 4.1 — Extração retroativa (v1)

```
scripts/run_extraction.py
  └── pipeline/extract.py: buscar_contatos(start_date, end_date)
        └── klaviyo/client.py: GET /api/profiles/?filter=created_at
              └── [paginação automática até esgotar resultados]
        └── Para cada contato:
              attribution/mapper.py: atribuir_origem(contato)
                ├── SE contato.properties tem utm_source
                │     └── retorna {origem, metodo: "propriedade_contato"}
                └── SENÃO
                      klaviyo/client.py: GET /api/events/?filter=profile_id
                        └── [ordena por data ASC, pega 1º com UTM]
                      ├── SE encontrou UTM no evento
                      │     └── retorna {origem, metodo: "evento_mais_antigo"}
                      └── SENÃO
                            └── retorna {origem: "Direto", metodo: "sem_utm"}
        └── supabase/client.py: upsert_lead(lead_data)
```

### 4.2 — Mapeamento UTM → Origem

Responsabilidade exclusiva de `src/attribution/rules.py`.

Lógica base (a ser expandida com regras reais da Minimal):
```
utm_medium == "cpc" AND utm_source == "google"   → Google
utm_medium == "cpc" AND utm_source in ["instagram", "facebook"] → Instagram/Facebook
utm_medium == "email" AND utm_source == "klaviyo" → Email Campanha / Email Fluxo
utm_source == "whatsapp"                          → WhatsApp (+ subtipo por campaign/flow)
utm_source == "influencer"                        → Influencer
...
(regras completas a serem definidas na sessão de implementação)
```

---

## 5. Decisões arquiteturais tomadas

| Decisão | Escolha | Motivo |
|---|---|---|
| Linguagem da pipeline | Python | Simplicidade, bibliotecas de HTTP maduras, `python-dotenv` |
| Banco de dados | Supabase (PostgreSQL) | Já definido como stack padrão. Suporta o futuro dashboard. |
| Chave de unicidade | `klaviyo_id` | Email pode mudar. ID do Klaviyo é estável. |
| Idempotência | Upsert por `klaviyo_id` | Extração pode ser re-rodada sem duplicar dados |
| Origem é imutável | Sem UPDATE após INSERT | Atribuição é um fato histórico, não deve mudar |
| V1 é retroativo puro | Sem webhook na v1 | Validar base primeiro. Webhook adiciona complexidade. |

---

## 6. Pontos frágeis conhecidos

| Ponto | Risco | Mitigação planejada |
|---|---|---|
| Rate limit Klaviyo | Muitas requisições de eventos podem ser bloqueadas (HTTP 429) | Backoff exponencial + retry no `KlaviyoClient` |
| Cobertura de UTM | ~23% têm UTM na propriedade. Fallback de evento pode não cobrir todos. | Aceitar `sem_utm` como resultado válido. Monitorar % de cobertura. |
| Regras de mapeamento UTM | Combinações de UTM desconhecidas → `Unassigned`. | Analisar UTMs brutos após extração e atualizar `rules.py`. |
| Volume de eventos por contato | Cada contato pode ter dezenas de eventos → muitas requisições | Buscar apenas o 1º evento com UTM (não todos). Paginação com limit=1 se a API permitir. |

---

## 7. Inventário de arquivos críticos

| Arquivo | Por que é crítico |
|---|---|
| `src/attribution/rules.py` | Define as 15 origens e o mapeamento. Erro aqui afeta toda a base. |
| `src/klaviyo/client.py` | Toda comunicação com o Klaviyo. Rate limit e paginação aqui. |
| `src/pipeline/extract.py` | Orquestrador. Define o fluxo completo de extração. |
| `supabase/migrations/001_create_leads.sql` | Schema da tabela principal. Mudança exige nova migration. |
| `src/config.py` | Fonte única de variáveis de ambiente. |
| `.env` | Credenciais reais. Nunca commitar. |

---

## 8. Próximos passos (Fase 2 — Esqueleto técnico)

1. Criar estrutura de pastas (`src/`, `scripts/`, `supabase/migrations/`, `docs/`)
2. Criar `requirements.txt`
3. Criar schema no Supabase (`supabase/migrations/001_create_leads.sql`)
4. Implementar `src/config.py`
5. Implementar `src/klaviyo/client.py` com chamada básica de listagem de contatos
6. Testar conexão com Klaviyo e Supabase antes de qualquer pipeline
