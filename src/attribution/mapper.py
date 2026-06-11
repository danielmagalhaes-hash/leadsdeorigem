from typing import Any
from urllib.parse import urlparse, parse_qs
from src.klaviyo.models import Contato, UTMs
from src.attribution.rules import _mapear

_TIPOS_ATIVO    = frozenset({"Active on Site"})
_TIPOS_FORM     = frozenset({"Form submitted by profile", "Form completed by profile"})
_TIPOS_LEAD_ADS = frozenset({"Filled Out Lead Ad"})


def _utms_diretas(props: dict[str, Any]) -> UTMs:
    return UTMs(
        source=props.get("utm_source"), medium=props.get("utm_medium"),
        campaign=props.get("utm_campaign"), content=props.get("utm_content"),
        term=props.get("utm_term"),
    )


def _utms_de_url(url: str) -> UTMs:
    params = parse_qs(urlparse(url).query)
    def _p(k: str) -> str | None:
        return (params.get(k) or [None])[0]
    return UTMs(source=_p("utm_source"), medium=_p("utm_medium"),
                campaign=_p("utm_campaign"), content=_p("utm_content"), term=_p("utm_term"))


def _buscar_em_tipos(eventos: list[dict], tipos: frozenset[str]) -> UTMs | None:
    for ev in eventos:
        if ev.get("_nome") in tipos:
            u = _utms_diretas(ev["attributes"].get("event_properties", {}))
            if u.tem_dados():
                return u
    return None


def _buscar_checkout(eventos: list[dict]) -> tuple[UTMs | None, str | None]:
    for ev in eventos:
        props = ev["attributes"].get("event_properties", {})
        landing = (props.get("$extra") or {}).get("full_landing_site") or props.get("full_landing_site")
        if landing:
            u = _utms_de_url(landing)
            if u.tem_dados():
                return u, landing
    return None, None


def _buscar_lead_ads(eventos: list[dict]) -> UTMs | None:
    for ev in eventos:
        if ev.get("_nome") in _TIPOS_LEAD_ADS:
            props = ev["attributes"].get("event_properties", {})
            u = UTMs(
                source=str(props.get("Platform") or "").lower() or None,
                medium="lead_ads",
                campaign=props.get("CampaignName"),
                content=props.get("AdName"),
                term=props.get("AdsetName"),
            )
            if u.tem_dados():
                return u
    return None


def detectar_origem_invalida(email: str | None, properties: dict) -> tuple[UTMs, str] | None:
    """Detecta origens que não passam pela busca de eventos. Retorna (utms, metodo) ou None."""
    if email and email.lower().endswith("@tiktokshop.com.br"):
        return UTMs(source="tik tok shop"), "integracao_tiktok"
    if "hs_object_source_label" in properties:
        return UTMs(source="lead criado no hubspot antigo"), "integracao_hubspot"
    return None


def extrair_utms_de_eventos(eventos: list[dict]) -> tuple[UTMs | None, str | None, str]:
    """Aplica as 4 prioridades com short-circuit. Retorna (utms, url_conversao, metodo)."""
    if u := _buscar_em_tipos(eventos, _TIPOS_ATIVO):
        return u, None, "ativo_no_site"
    if u := _buscar_em_tipos(eventos, _TIPOS_FORM):
        return u, None, "formulario"
    u, url = _buscar_checkout(eventos)
    if u:
        return u, url, "checkout"
    if u := _buscar_lead_ads(eventos):
        return u, None, "lead_ads"
    return None, None, "sem_utm"


def atribuir_origem(contato: Contato, evento_mais_antigo_utms: UTMs | None = None) -> dict[str, Any]:
    if contato.utms_propriedade.tem_dados():
        utms = contato.utms_propriedade
        metodo = "propriedade_contato"
    elif evento_mais_antigo_utms and evento_mais_antigo_utms.tem_dados():
        utms = evento_mais_antigo_utms
        metodo = "evento_mais_antigo"
    else:
        utms = UTMs()
        metodo = "sem_utm"

    origem = _mapear(utms.source, utms.medium, utms.campaign)

    return {
        "origem": origem,
        "metodo_atribuicao": metodo,
        "utm_source": utms.source,
        "utm_medium": utms.medium,
        "utm_campaign": utms.campaign,
        "utm_content": utms.content,
        "utm_term": utms.term,
    }
