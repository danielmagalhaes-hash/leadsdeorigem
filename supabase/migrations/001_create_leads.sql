-- Migration 001: Tabela principal de leads com origem atribuída
-- Projeto: Leads de Origem | Minimal Club

CREATE TABLE IF NOT EXISTS leads (
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
  metodo_atribuicao   TEXT NOT NULL CHECK (
    metodo_atribuicao IN ('propriedade_contato', 'evento_mais_antigo', 'sem_utm')
  ),
  processado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_criado_em ON leads (criado_em);
CREATE INDEX IF NOT EXISTS idx_leads_origem    ON leads (origem);
