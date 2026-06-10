"""
Amostra 50 leads com lógica v2 de atribuição por 3 prioridades:
1. Ativo no site (Active on Site) - mais antigo com UTM direto
2. Formulário preenchido - mais antigo com UTM direto
3. Checkout iniciado - mais antigo com full_landing_site (extrai UTMs da URL)

Grava na tabela leads_v2 (inclui url_conversao).
"""
import sys, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import httpx
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, timedelta

_BRT = timezone(timedelta(hours=-3))

def _para_brt(dt_str: str) -> str:
    return datetime.fromisoformat(dt_str).astimezone(_BRT).isoformat()
from src.config import settings
from src.klaviyo.client import _extrair_utms_de_propriedades
from src.klaviyo.models import Contato, UTMs
from src.attribution.mapper import atribuir_origem
from supabase import create_client

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
h = {
    "Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY,
    "revision": "2024-02-15",
    "accept": "application/json",
}

_TIPOS_ATIVO     = {"Active on Site"}
_TIPOS_FORM      = {"Form submitted by profile", "Form completed by profile"}
_TIPOS_LEAD_ADS  = {"Filled Out Lead Ad"}


def _utms_de_url(url: str) -> UTMs:
    params = parse_qs(urlparse(url).query)
    def _p(k: str) -> str | None:
        return (params.get(k) or [None])[0]
    return UTMs(source=_p("utm_source"), medium=_p("utm_medium"),
                campaign=_p("utm_campaign"), content=_p("utm_content"), term=_p("utm_term"))


def _utms_diretas(props: dict) -> UTMs:
    return UTMs(source=props.get("utm_source"), medium=props.get("utm_medium"),
                campaign=props.get("utm_campaign"), content=props.get("utm_content"),
                term=props.get("utm_term"))


def _buscar_todos_eventos(klaviyo_id: str) -> list:
    url = "https://a.klaviyo.com/api/events/"
    params = {
        "filter": f'equals(profile_id,"{klaviyo_id}")',
        "page[size]": 50,
        "fields[event]": "datetime,event_properties",
        "include": "metric",
        "fields[metric]": "name",
    }
    todos = []
    while url:
        r = httpx.get(url, headers=h, params=params, timeout=15)
        r.raise_for_status()
        dados = r.json()
        # Monta índice metric_id → nome
        metricas = {m["id"]: m["attributes"]["name"] for m in dados.get("included", [])}
        for ev in dados.get("data", []):
            metric_id = (ev.get("relationships", {}).get("metric", {}).get("data") or {}).get("id")
            ev["_event_name"] = metricas.get(metric_id, "")
        todos.extend(dados.get("data", []))
        url = (dados.get("links") or {}).get("next")
        params = {}
    return sorted(todos, key=lambda e: e.get("attributes", {}).get("datetime", ""))


def buscar_utms_v2(klaviyo_id: str) -> tuple[UTMs | None, str | None, str]:
    """Retorna (utms, url_conversao, metodo) com metodo = ativo_no_site | formulario | checkout | sem_utm."""
    eventos = _buscar_todos_eventos(klaviyo_id)

    # Prioridade 1: Active on Site
    for ev in eventos:
        if ev.get("_event_name") in _TIPOS_ATIVO:
            utms = _utms_diretas(ev["attributes"].get("event_properties", {}))
            if utms.tem_dados():
                return utms, None, "ativo_no_site"

    # Prioridade 2: Formulário
    for ev in eventos:
        if ev.get("_event_name") in _TIPOS_FORM:
            utms = _utms_diretas(ev["attributes"].get("event_properties", {}))
            if utms.tem_dados():
                return utms, None, "formulario"

    # Prioridade 3: Checkout com full_landing_site (dentro de $extra)
    for ev in eventos:
        props = ev["attributes"].get("event_properties", {})
        extra = props.get("$extra") or {}
        url_landing = extra.get("full_landing_site") or props.get("full_landing_site")
        if url_landing:
            utms = _utms_de_url(url_landing)
            if utms.tem_dados():
                return utms, url_landing, "checkout"

    # Prioridade 4: Facebook / Instagram Lead Ads
    for ev in eventos:
        if ev.get("_event_name") in _TIPOS_LEAD_ADS:
            props = ev["attributes"].get("event_properties", {})
            platform = str(props.get("Platform") or "").lower()
            utms = UTMs(
                source=platform or None,
                medium="lead_ads",
                campaign=props.get("CampaignName"),
                content=props.get("AdName"),
                term=props.get("AdsetName"),
            )
            if utms.tem_dados():
                return utms, None, "lead_ads"

    return None, None, "sem_utm"


# --- Busca os 50 leads ---
r = httpx.get("https://a.klaviyo.com/api/profiles/", headers=h,
    params={"filter": "greater-than(created,2026-06-07T00:00:00+00:00)",
            "page[size]": 50, "fields[profile]": "email,created,properties"}, timeout=30)
leads_raw = r.json().get("data", [])
print(f"Leads retornados: {len(leads_raw)}\n")

registros = []
stats = {"propriedade_contato": 0, "ativo_no_site": 0, "formulario": 0, "checkout": 0, "lead_ads": 0, "sem_utm": 0}

for item in leads_raw:
    attrs = item.get("attributes", {})
    contato = Contato(
        klaviyo_id=item["id"],
        email=attrs.get("email"),
        criado_em=_para_brt(attrs.get("created")),
        utms_propriedade=_extrair_utms_de_propriedades(attrs.get("properties", {})),
    )

    evento_utms, url_conversao, metodo_evento = None, None, "sem_utm"
    if not contato.utms_propriedade.tem_dados():
        evento_utms, url_conversao, metodo_evento = buscar_utms_v2(contato.klaviyo_id)
        time.sleep(0.1)

    atribuicao = atribuir_origem(contato, evento_utms)

    # Substitui metodo_atribuicao pelo método granular
    if atribuicao["metodo_atribuicao"] == "evento_mais_antigo":
        atribuicao["metodo_atribuicao"] = metodo_evento
    stats[atribuicao["metodo_atribuicao"]] += 1

    source = atribuicao.get("utm_source") or "(null)"
    metodo = atribuicao["metodo_atribuicao"]
    print(f"{contato.criado_em[:10]} | {metodo:<22} | source: {source}")
    if url_conversao:
        print(f"  checkout url: {url_conversao[:90]}")

    registros.append({
        "klaviyo_id": contato.klaviyo_id,
        "email": contato.email,
        "criado_em": contato.criado_em,
        **atribuicao,
        "url_conversao": url_conversao,
    })

db.table("leads_v2").upsert(registros, on_conflict="klaviyo_id").execute()

total = len(registros)
com_utm = total - stats["sem_utm"]
cobertura = round(com_utm / total * 100, 1)
print(f"\n=== RESUMO V2 ===")
print(f"Total:                   {total}")
print(f"Via propriedade:         {stats['propriedade_contato']}")
print(f"Via ativo no site:       {stats['ativo_no_site']}")
print(f"Via formulário:          {stats['formulario']}")
print(f"Via checkout:            {stats['checkout']}")
print(f"Via lead ads:            {stats['lead_ads']}")
print(f"Sem UTM:                 {stats['sem_utm']}")
print(f"Cobertura total:         {cobertura}%")
