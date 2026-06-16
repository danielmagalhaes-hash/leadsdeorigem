from typing import Optional

_META_SOURCES   = frozenset({"instagram", "facebook", "fb", "facebo", "ig"})
_WPP_FLUXO      = frozenset({"whatsapp_fluxo", "whatsapp_fluxo_ia", "fluxos_crm"})
_EMAIL_FLUXO    = frozenset({"email_fluxo", "fluxos_crm"})


def _mapear(source: Optional[str], medium: Optional[str], campaign: Optional[str]) -> str:
    s = (source or "").lower().strip()
    m = (medium or "").lower().strip()
    c = (campaign or "").lower().strip()

    if not s and not m and not c:
        return "Direto"

    # Google Institucional — campanha específica, prioridade máxima
    if "c16_search_branded_exata_sr" in c:
        return "Google Institucional"

    # Meta Ads — source instagram/facebook + medium cpc/paid
    _is_meta = s in _META_SOURCES or s.startswith("instagram") or s.startswith("facebook") or s.startswith("facebo")
    if _is_meta and ("cpc" in m or "paid" in m):
        return "Meta Ads"

    # WhatsApp — diferenciado pelo medium
    if s == "whatsapp":
        if m in _WPP_FLUXO:
            return "WhatsApp Fluxo"
        if m == "whatsapp_campanha":
            return "WhatsApp Campanha"
        if m == "comunidade":
            return "WhatsApp Comunidade"

    # E-mail — diferenciado pelo medium
    if s == "email":
        if m in _EMAIL_FLUXO:
            return "E-mail Fluxo"
        if m == "email_campanha":
            return "E-mail Campanha"

    # Comercial
    if s == "comercial":
        return "Comercial"

    # Google
    if s in ("google", "adwords"):
        return "Google"

    # Social
    if m == "social":
        return "Social"

    # Influenciadores
    if "influencer" in m or "influenciador" in m:
        return "Influenciadores"

    # B2B — Lead Ads (ig/fb/outros)
    if m == "lead_ads":
        return "B2B"

    # Tem UTM mas não casou com nenhuma regra
    return "Outros canais"


ORIGENS_VALIDAS = {
    "Meta Ads",
    "Google Institucional",
    "Google",
    "Social",
    "Influenciadores",
    "B2B",
    "WhatsApp Fluxo",
    "WhatsApp Campanha",
    "WhatsApp Comunidade",
    "E-mail Fluxo",
    "E-mail Campanha",
    "Comercial",
    "Outros canais",
    "Direto",
}
