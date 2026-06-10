from typing import Optional

# Tabela de mapeamento UTM → Origem
# Formato: lista de (condição_fn, nome_origem) avaliada em ordem.
# Primeira regra que bater vence.

def _mapear(source: Optional[str], medium: Optional[str], campaign: Optional[str]) -> str:
    s = str(source or "").lower()
    m = str(medium or "").lower()
    c = str(campaign or "").lower()

    if not s and not m:
        return "Direto"

    if s in ("instagram", "facebook", "ig", "fb") or (m == "social" and s in ("instagram", "facebook")):
        return "Instagram/Facebook"

    if s == "google" and "institucional" in c:
        return "Google Institucional"

    if s == "google":
        return "Google"

    if s == "klaviyo" and m == "email" and "flow" in c:
        return "Email Fluxo"

    if m == "email" or s in ("email", "klaviyo"):
        return "Email Campanha"

    if s == "whatsapp" and "flow" in c:
        return "WhatsApp Fluxo"

    if s == "whatsapp" and m == "campaign":
        return "WhatsApp Campanha"

    if s == "whatsapp":
        return "WhatsApp"

    if s == "influencer" or m == "influencer":
        return "Influencer"

    if m in ("organic", "organico", "seo"):
        return "Orgânico"

    if m in ("social", "social-media"):
        return "Social"

    if s in ("auto-referral", "auto_referral") or m == "referral":
        return "Auto Referral"

    if s == "comercial" or m == "comercial":
        return "Comercial"

    return "Unassigned"


ORIGENS_VALIDAS = {
    "Google Institucional",
    "Instagram/Facebook",
    "Google",
    "Email Campanha",
    "Direto",
    "Social",
    "Orgânico",
    "Unassigned",
    "Auto Referral",
    "Email Fluxo",
    "WhatsApp",
    "Comercial",
    "WhatsApp Campanha",
    "WhatsApp Fluxo",
    "Influencer",
}
