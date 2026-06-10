# CLAUDE.md — Leads de Origem

> Manual de operação do agente. Ler inteiro no início de toda sessão.

---

## 1. Stack do projeto

| Camada | Tecnologia | Versão |
|---|---|---|
| Pipeline de dados | Python | 3.11+ |
| Banco de dados | Supabase (PostgreSQL) | — |
| Cliente Supabase | supabase-py | 2.x |
| HTTP (Klaviyo API) | httpx | — |
| Variáveis de ambiente | python-dotenv | — |
| Futuro (dashboard) | Next.js + Vercel | — |

---

## 2. Glossário resumido

| Termo | Definição curta |
|---|---|
| **Lead** | Novo contato criado no Klaviyo pela 1ª vez |
| **Origem** | Uma das 15 categorias fixas de canal de aquisição |
| **UTM** | Parâmetros de URL: source, medium, campaign, content, term |
| **Propriedade de contato** | Campo do perfil do contato no Klaviyo com UTMs gravados |
| **Evento mais antigo** | Fallback: 1º evento do contato no Klaviyo com UTM no metadata |
| **Cobertura de UTM** | % da base com origem identificada (meta: >80%) |
| **Retroativo** | Extração histórica de um intervalo de datas passadas |
| **metodo_atribuicao** | Como a origem foi determinada: `propriedade_contato`, `evento_mais_antigo`, `sem_utm` |
| **Last Click** | Modelo antigo (Shopify checkout). Este sistema o substitui. |

---

## 3. Regras invioláveis

1. **Nunca commitar `.env`.** Credenciais ficam apenas no `.env` local. O `.gitignore` já protege, mas é sua responsabilidade verificar antes de cada commit.

2. **Todo acesso à API do Klaviyo passa pelo `KlaviyoClient`.** Nunca fazer chamada HTTP direta fora da classe cliente. Toda chamada tem retry e backoff automáticos.

3. **Origem é imutável após atribuição.** Uma vez gravada no Supabase, a origem de um lead nunca é alterada. Reconversões são ignoradas.

4. **Lead é identificado pelo `klaviyo_id`, nunca pelo email.** O email pode mudar. O `klaviyo_id` é a chave de integração.

5. **Funções com no máximo 20 linhas.** Se cresceu além disso, extrair sub-função com nome que descreva o que faz.

6. **Sem `any`, sem type hints faltando.** Todo parâmetro e retorno de função tem tipo declarado.

7. **Sem silenciar erros.** `except Exception: pass` é proibido. Toda exceção é logada com contexto (qual lead, qual endpoint, qual status code).

8. **Variáveis de ambiente carregadas apenas em `config.py`.** Nenhum outro módulo importa `os.environ` ou `dotenv` diretamente.

---

## 4. Padrões de implementação canônicos

### 4.1 — Chamada à API do Klaviyo

```python
# CORRETO: usar KlaviyoClient com retry automático
from src.klaviyo.client import KlaviyoClient

client = KlaviyoClient()
contacts = client.get_contacts(start_date="2026-06-01", end_date="2026-06-09")
```

```python
# ERRADO: nunca chamar httpx diretamente no pipeline
import httpx
response = httpx.get("https://a.klaviyo.com/api/profiles/")  # proibido fora do cliente
```

### 4.2 — Atribuição de origem

```python
# CORRETO: usar o mapper centralizado
from src.attribution.mapper import atribuir_origem

resultado = atribuir_origem(contato)
# retorna: {"origem": "Instagram/Facebook", "metodo_atribuicao": "propriedade_contato", "utms": {...}}
```

```python
# ERRADO: lógica de mapeamento inline no pipeline
if "instagram" in utm_source:  # nunca espalhar regras de negócio fora do mapper
    origem = "Instagram/Facebook"
```

### 4.3 — Inserção no Supabase

```python
# CORRETO: usar upsert com klaviyo_id como chave
from src.supabase.client import SupabaseClient

db = SupabaseClient()
db.upsert_lead(lead_data)  # usa klaviyo_id como constraint de unicidade
```

### 4.4 — Variáveis de ambiente

```python
# CORRETO: importar de config.py
from src.config import settings

api_key = settings.KLAVIYO_API_KEY
```

```python
# ERRADO: acessar diretamente
import os
api_key = os.environ.get("KLAVIYO_API_KEY")  # proibido fora de config.py
```

### 4.5 — Logging

```python
# CORRETO: log estruturado com contexto
import logging
logger = logging.getLogger(__name__)

logger.info("Lead processado", extra={"klaviyo_id": lead_id, "origem": origem})
logger.error("Erro ao buscar eventos", extra={"klaviyo_id": lead_id, "status_code": 429})
```

---

## 5. Anti-patterns

| Anti-pattern | Por quê é ruim | Alternativa |
|---|---|---|
| Silenciar exceções (`except: pass`) | Erros desaparecem sem deixar rastro | Logar sempre com contexto |
| Hardcodar datas no código | Muda toda vez que roda | Usar `settings.EXTRACTION_START_DATE` |
| Fazer N chamadas síncronas sem controle | Estoura rate limit do Klaviyo | Usar backoff exponencial no `KlaviyoClient` |
| Lógica de origem espalhada | Impossível auditar o mapeamento | Tudo em `src/attribution/mapper.py` |
| Commitar `.env` | Expõe credenciais no GitHub | Verificar `git status` antes de `git push` |
| Usar email como chave | Email pode mudar ou ser reutilizado | Sempre usar `klaviyo_id` |

---

## 6. Estrutura de pastas

```
leadsdeorigem/
├── .env                      # Credenciais locais (nunca commitar)
├── .env.example              # Template das variáveis necessárias
├── .gitignore
├── requirements.txt          # Dependências Python
├── PRODUCT.md                # Fonte de verdade do domínio
├── CLAUDE.md                 # Este arquivo
├── ARCHITECTURE.md           # Mapa do sistema
│
├── src/
│   ├── config.py             # Carrega variáveis de ambiente
│   ├── klaviyo/
│   │   ├── client.py         # Cliente HTTP com retry/backoff
│   │   └── models.py         # Tipos do Klaviyo (contato, evento)
│   ├── supabase/
│   │   └── client.py         # Cliente Supabase
│   ├── attribution/
│   │   ├── mapper.py         # Lógica de UTM → Origem (15 categorias)
│   │   └── rules.py          # Tabela de mapeamento UTM → Origem
│   └── pipeline/
│       └── extract.py        # Orquestra o fluxo de extração
│
├── supabase/
│   └── migrations/           # Arquivos SQL de schema
│
├── scripts/
│   └── run_extraction.py     # Entry point: python scripts/run_extraction.py
│
└── docs/
    ├── sessions/             # Logs de sessão (YYYY-MM-DD-tema.md)
    ├── specs/                # Specs de features
    └── decisions/            # ADRs
```

---

## 7. Como rodar

```bash
# 1. Criar e ativar ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Preencher o .env com as credenciais reais

# 4. Rodar extração retroativa (v1)
python scripts/run_extraction.py
```

---

## 8. Como depurar

**Problema: rate limit do Klaviyo (HTTP 429)**
→ O `KlaviyoClient` já faz retry automático com backoff. Se persistir, verificar nos logs quantas requisições estão sendo feitas por segundo.

**Problema: lead sem UTM após propriedade + fallback**
→ Verificar no Klaviyo se o contato tem eventos registrados. Se não tiver nenhum evento, `metodo_atribuicao = sem_utm` é o resultado correto.

**Problema: cobertura baixa (muitos `sem_utm`)**
→ Analisar `metodo_atribuicao` na base: `SELECT metodo_atribuicao, COUNT(*) FROM leads GROUP BY metodo_atribuicao`. Se maioria é `sem_utm`, o fallback de evento não está encontrando UTMs — investigar se os eventos têm metadata de UTM.

**Problema: origem `Unassigned` alta**
→ Verificar UTMs brutos no Supabase. Provavelmente há uma combinação nova de source/medium que precisa ser adicionada em `src/attribution/rules.py`.
