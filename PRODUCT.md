# PRODUCT.md — Leads de Origem

> Documento vivo. Atualizar sempre que o produto mudar. É a fonte de verdade do domínio.

---

## 1. Visão e proposta de valor

**Problema:**
A Minimal Club atribui vendas e leads ao canal de origem pelo modelo Last Click — o último canal registrado no checkout da Shopify. Esse modelo distorce a visão real de como os leads são gerados: um lead que entrou na base pelo Instagram três meses atrás pode ser atribuído ao Google no momento da compra.

**Solução:**
Leads de Origem é uma base de dados que registra a **origem real** de cada novo lead do Klaviyo — baseada no primeiro ponto de contato identificável via UTM — permitindo à gestão da Minimal tomar decisões de investimento em canais com base em dados completos, não apenas no último clique.

**Proposta de valor em uma frase:**
> Leads de Origem dá à gestão da Minimal clareza sobre quais canais realmente geram leads, indo além do Last Click do Shopify.

---

## 2. Usuários e papéis

| Usuário | Papel | O que precisa |
|---|---|---|
| **Daniel Magalhães** | Admin / CRM | Controle total do sistema. Responsável pelo volume total de leads gerados. Orquestra os times de Performance e Social. |
| **Time de Performance** | Mídia paga | Visualizar leads gerados pelos canais pagos (Google, Meta). Entender quais campanhas e anúncios convertem mais leads. |
| **Time de Social** | Social orgânico | Visualizar leads gerados pelo social orgânico e influenciadores. |
| **Gestão da Minimal** | Diretoria | Dashboard executivo com visão agregada para decisões estratégicas de alocação de investimento. |

**Regra de acesso (v1):**
Na v1, Daniel é o único usuário ativo. Permissões por papel serão implementadas quando o dashboard for construído.

---

## 3. Glossário do domínio

| Termo | Definição | Exemplo |
|---|---|---|
| **Lead** | Novo contato criado no Klaviyo pela primeira vez. Reconversões no mesmo email não geram novo lead. | Pessoa que preenche formulário pela 1ª vez no site da Minimal. |
| **Origem** | Agrupamento predefinido que representa o canal real de aquisição do lead, derivado da combinação de UTMs. São 15 categorias fixas. | `utm_source=instagram` + `utm_medium=social` → Origem: **Instagram/Facebook** |
| **UTM** | Parâmetros de URL que identificam a fonte de tráfego: `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`. | `?utm_source=google&utm_medium=cpc&utm_campaign=brand` |
| **Last Click** | Modelo de atribuição atual: o canal registrado no checkout da Shopify no momento da compra recebe 100% do crédito. | Cliente vê anúncio no Instagram, pesquisa no Google e compra → Google recebe o crédito. |
| **Propriedade de contato** | Campo fixo gravado no perfil do contato dentro do Klaviyo. UTMs de origem ficam aqui quando o lead entra via formulário. | `$source`, `utm_source`, `utm_medium` no perfil do contato Klaviyo. |
| **Evento mais antigo** | O registro de atividade mais antigo de um contato no Klaviyo. Usado como fallback para extrair UTM quando a propriedade de contato não tem esse dado. | Evento `Opened Email` de 15/05 com UTM no metadata → origem inferida daí. |
| **Cobertura de UTM** | Percentual da base de leads que tem origem identificada. Indicador de qualidade da base. Meta: alta cobertura (>80%). | Hoje: ~23% via propriedade de contato. |
| **Retroativo** | Extração histórica de leads para um período passado, para popular a base inicial. | Extração de todos os leads criados entre 01/06 e 09/06/2026. |
| **Fallback de evento** | Estratégia de atribuição: quando a propriedade de contato não tem UTM, busca-se o evento mais antigo do contato para inferir a origem. | Contato sem `utm_source` na propriedade → busca evento mais antigo → extrai UTM do metadata. |

---

## 4. Origens (15 categorias fixas)

As origens são fixas e definidas pela equipe da Minimal. O mapeamento UTM → Origem é a lógica central do sistema.

| Origem | Descrição |
|---|---|
| Google Institucional | Tráfego de Google Ads para páginas institucionais da marca |
| Instagram/Facebook | Tráfego pago ou orgânico de Meta (Instagram + Facebook) |
| Google | Google Ads genérico (search, display, shopping) |
| Email Campanha | Leads vindos de campanhas de email marketing |
| Direto | Acesso direto ao site (sem UTM identificável) |
| Social | Redes sociais orgânicas (exceto Instagram/Facebook categorizados separadamente) |
| Orgânico | Busca orgânica (SEO) |
| Unassigned | UTM presente mas não mapeado para nenhuma categoria |
| Auto Referral | Tráfego interno entre domínios da própria Minimal |
| Email Fluxo | Leads ativados por fluxos automáticos de email (Klaviyo flows) |
| WhatsApp | WhatsApp comunidade |
| Comercial | Leads inseridos manualmente pelo time comercial |
| WhatsApp Campanha | Campanhas ativas de WhatsApp |
| WhatsApp Fluxo | Fluxos automáticos de WhatsApp |
| Influencer | Tráfego originado de links de influenciadores |

> **Regra:** Se nenhum UTM for encontrado após propriedade + fallback de evento → Origem = **Direto**.
> Se UTM existir mas não mapear para nenhuma categoria → Origem = **Unassigned**.

---

## 5. Entidades do negócio

### 5.1 Lead

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | UUID | Identificador interno |
| `klaviyo_id` | string | ID do contato no Klaviyo (chave de integração) |
| `email` | string | Email do contato |
| `criado_em` | timestamp | Data/hora de criação do contato no Klaviyo |
| `origem` | enum (15 valores) | Categoria de origem atribuída |
| `utm_source` | string | Valor bruto do utm_source |
| `utm_medium` | string | Valor bruto do utm_medium |
| `utm_campaign` | string | Valor bruto do utm_campaign |
| `utm_content` | string | Valor bruto do utm_content |
| `utm_term` | string | Valor bruto do utm_term |
| `metodo_atribuicao` | enum | `propriedade_contato` ou `evento_mais_antigo` ou `sem_utm` |
| `processado_em` | timestamp | Quando o sistema atribuiu a origem |

**Ciclo de vida:**
- Criado: quando extraído do Klaviyo (retroativo) ou via webhook (futuro)
- Nunca atualizado: origem é imutável após atribuição
- Nunca deletado

### 5.2 Evento Klaviyo (tabela de apoio — v1)

Usado temporariamente durante a extração retroativa para encontrar o evento mais antigo.

| Campo | Tipo | Descrição |
|---|---|---|
| `klaviyo_id` | string | ID do contato |
| `tipo_evento` | string | Nome do evento no Klaviyo |
| `ocorrido_em` | timestamp | Data do evento |
| `utm_source` | string | UTM extraído do metadata do evento |
| `utm_medium` | string | UTM extraído do metadata do evento |
| `utm_campaign` | string | UTM extraído do metadata do evento |

---

## 6. Fluxos principais

### Fluxo 1 — Extração retroativa (v1)

**Objetivo:** Popular a base com leads do período 01/06 a 09/06/2026 com alta cobertura de UTM.

**Pré-condição:** Klaviyo API Key configurada, Supabase com schema criado.

**Passos:**
1. Buscar todos os contatos do Klaviyo criados entre 01/06 e 09/06
2. Para cada contato:
   a. Verificar propriedade de contato → tem UTM? → atribuir origem, `metodo_atribuicao = propriedade_contato`
   b. Não tem UTM na propriedade → buscar eventos do contato → pegar o mais antigo com UTM → atribuir origem, `metodo_atribuicao = evento_mais_antigo`
   c. Nenhum UTM encontrado → `metodo_atribuicao = sem_utm`, `origem = Direto`
3. Mapear UTMs brutos → Origem (15 categorias)
4. Gravar no Supabase

**Pós-condição:** Base com todos os leads do período, cobertura de UTM máxima alcançável, pronta para análise.

**Atenção técnica:** Klaviyo API tem rate limit. A extração de eventos por contato é custosa (1 requisição por contato). Implementar controle de backoff e retry.

### Fluxo 2 — Atribuição de origem (lógica central)

**Entrada:** Contato do Klaviyo (com ou sem UTM na propriedade)

**Lógica:**
```
SE propriedade de contato tem utm_source
  → usar UTMs da propriedade
  → metodo_atribuicao = "propriedade_contato"

SENÃO
  → buscar eventos ordenados por data ASC
  → pegar primeiro evento com utm_source no metadata
  → SE encontrado: usar esses UTMs, metodo_atribuicao = "evento_mais_antigo"
  → SE não encontrado: utm vazio, metodo_atribuicao = "sem_utm"

→ Mapear utm_source + utm_medium → Origem (15 categorias)
→ SE não mapear → Origem = "Unassigned"
→ SE sem utm → Origem = "Direto"
```

### Fluxo 3 — Captura em tempo real (pós-v1)

**Trigger:** Novo contato criado no Klaviyo (webhook)

**Passos:**
1. Klaviyo envia webhook com dados do novo contato
2. Sistema executa Fluxo 2 (atribuição de origem)
3. Grava lead na base

---

## 7. KPIs

| KPI | Fórmula | Uso |
|---|---|---|
| **Total de leads** | `COUNT(leads) WHERE criado_em BETWEEN data_inicio AND data_fim` | Acompanhamento de crescimento |
| **Leads por origem** | `COUNT(leads) GROUP BY origem` | Entender quais canais geram mais leads |
| **Leads por dia** | `COUNT(leads) GROUP BY DATE(criado_em)` | Identificar sazonalidade e picos |
| **Cobertura de UTM** | `COUNT(leads WHERE metodo_atribuicao != 'sem_utm') / COUNT(leads) * 100` | Qualidade da base. Meta: >80% |
| **Top canais** | `COUNT(leads) GROUP BY origem ORDER BY count DESC` | Ranking de canais por volume |

---

## 8. Escopo

### V1 — Validação da base (NOW)
- Extração retroativa: 01/06/2026 a 09/06/2026
- Alta cobertura de UTM via propriedade de contato + fallback de evento
- Base estruturada no Supabase com todas as dimensões de UTM
- Análise básica: leads/dia e top canais por origem
- Validação da qualidade e cobertura antes de qualquer dashboard

### Futuro — Após validação da v1
- Webhook em tempo real para captura de novos leads
- Dashboard visual publicado na Vercel
- Drill-down por campanha, anúncio (`utm_content`) e palavra-chave (`utm_term`)
- Expansão do período retroativo para toda a base histórica
- Visões por usuário (Performance, Social, Gestão)

### Nunca (fora de escopo)
- Lead scoring ou qualificação de leads
- Integração direta com Shopify para cruzar leads com vendas/receita
- Comparação automática Last Click vs Origem (pode ser análise manual)
- CRM completo ou gestão de pipeline de vendas

---

## 9. Restrições e premissas

| Restrição | Detalhe |
|---|---|
| **Klaviyo API rate limit** | Extração de eventos por contato é custosa. Necessário controle de backoff, retry e paginação. |
| **Cobertura inicial baixa** | Apenas ~23% da base tem UTM na propriedade de contato. O fallback de evento aumenta a cobertura, mas não garante 100%. |
| **Checkout sem UTM** | Leads que entram exclusivamente via checkout Shopify (sem formulário) podem não ter UTM em nenhuma propriedade nem evento. |
| **Origem é imutável** | Uma vez atribuída, a origem do lead não muda. Reconversões são ignoradas. |
| **GitHub** | Código versionado no GitHub. `.env` nunca sobe para o repositório (protegido no `.gitignore`). |
| **Stack** | Python (pipeline de dados) + Supabase (banco de dados) + Vercel (futuro dashboard). |
| **V1 é validação** | Dashboard e painel só serão construídos após validação clara da qualidade da base gerada na v1. |
