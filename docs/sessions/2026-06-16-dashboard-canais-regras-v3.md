# Sessão 2026-06-16 — Dashboard de canais + Regras de atribuição v3

## Objetivo
Construir o dashboard de aquisição de leads com dados reais do Supabase e acertar o agrupamento de canais.

---

## O que foi feito

### 1. Dashboard (leads-crm.html)
- Removido todo o mock data — dashboard agora carrega `dashboard_data.json` via `fetch()` assíncrono
- Adicionado filtro de **data personalizada** (De / Até) além dos períodos fixos (7d, 30d, 60d, 90d, MTD)
- **Bloco 1 redesenhado** — 4 cards:
  - **Leads no período** — total filtrado pelo período selecionado + Δ vs período anterior
  - **Média / dia** — total ÷ dias + Δ vs período anterior
  - **MTD** — acumulado do mês com Δ vs mesmo período do mês passado
  - **Meta** — campos editáveis (meta do mês + meta do dia), barra de progresso MTD, projeção fim do mês; valores persistidos em localStorage
- Removidos: "Leads hoje", "% da meta diária", "Projeção 90d" (não faziam sentido com base atualizada 1×/dia)

### 2. Gerador de dados (scripts/gerar_dashboard_data.py)
- Busca os últimos 90 dias de `leads_v2` (excluindo `integracao_hubspot` e `integracao_tiktok`)
- Busca período anterior (90-180d) para calcular Δ dos UTMs
- Agrega por canal/dia em BRT e exporta `dashboard_data.json`
- Calcula baseline (mediana 60d) e meta automática (baseline × 1,5) como fallback se o usuário não definir meta manual

### 3. Regras de atribuição v3 (src/attribution/rules.py)
Regras novas, em ordem de prioridade:

| Canal | Critério |
|---|---|
| Direto | sem utm_source, utm_medium, utm_campaign |
| Google Institucional | utm_campaign contém `c16_search_branded_exata_sr` |
| Meta Ads | source: instagram/facebook/fb/facebo/ig + medium: cpc ou paid |
| WhatsApp Fluxo | source: whatsapp + medium: whatsapp_fluxo / whatsapp_fluxo_ia / fluxos_crm |
| WhatsApp Campanha | source: whatsapp + medium: whatsapp_campanha |
| WhatsApp Comunidade | source: whatsapp + medium: comunidade |
| E-mail Fluxo | source: email + medium: email_fluxo / fluxos_crm |
| E-mail Campanha | source: email + medium: email_campanha |
| Comercial | source: comercial |
| Google | source: google / adwords |
| Social | medium: social |
| Influenciadores | medium contém influencer / influenciador |
| B2B | medium: lead_ads (qualquer source) |
| Outros canais | tem UTM mas não bateu em nenhuma regra |

### 4. Migration do banco
- UPDATE em **55.331 registros** na `leads_v2` com as novas regras (via SQL direto no Supabase)
- Distribuição final:

| Canal | Leads |
|---|---|
| Meta Ads | 23.086 |
| Google | 9.680 |
| Social | 5.885 |
| Direto | 5.786 |
| Google Institucional | 3.700 |
| B2B | 2.206 |
| WhatsApp Campanha | 1.802 |
| Influenciadores | 1.370 |
| Outros canais | 918 |
| WhatsApp Fluxo | 375 |
| E-mail Campanha | 169 |
| E-mail Fluxo | 155 |
| WhatsApp Comunidade | 134 |
| Comercial | 65 |

### 5. Infraestrutura local
- `abrir_dashboard.bat` — duplo clique: gera o JSON e abre http://localhost:8080/leads-crm.html
- `tzdata` adicionado ao `requirements.txt` (necessário no Windows para `zoneinfo`)
- Servidor HTTP embutido (`python -m http.server 8080`) servindo os arquivos localmente

---

## Decisões tomadas

| Decisão | Motivo |
|---|---|
| Excluir `integracao_hubspot` (124k) e `integracao_tiktok` (2k) do dashboard | São imports do CRM antigo, não aquisição orgânica real |
| `lead_ads` → B2B (não Meta Ads) | ig/fb + lead_ads são Lead Ads B2B, canal distinto do paid social de consumo |
| Meta do mês e meta do dia são inputs manuais | Baseline automático (×1,5) serve como referência, mas a meta real é definida pelo time |
| localStorage para persistir metas | Evita preencher toda vez; simples e sem backend adicional |

---

## Estado atual
- Pipeline extrai diariamente novos leads com as regras v3
- Base histórica (90d) atualizada com as novas origens
- Dashboard funcional localmente em http://localhost:8080/leads-crm.html
- Período anterior (90-180d) retorna 0 leads — extração retroativa cobre apenas os últimos ~90 dias

---

## Próximos passos sugeridos

1. **Extração retroativa maior** — rodar extração para cobrir 180d+ e habilitar o Δ de período anterior no dashboard
2. **Deploy do dashboard** — hospedar o dashboard em Vercel ou similar para acesso sem servidor local
3. **Cron automático no servidor** — agendar `gerar_dashboard_data.py` para rodar após o cron de extração (~02h30)
4. **Funil completo** — conectar dados de sessão (GA4 ou similar) para calcular taxa de conversão sessão → lead por canal
