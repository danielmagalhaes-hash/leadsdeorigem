"""
Amostra 50 leads v3: atribui UTM pelo evento mais antigo NO DIA DA CRIAÇÃO (em BRT).

Diferença vs v2: em vez de pegar o evento mais antigo de todos os tempos,
filtra apenas os eventos que ocorreram no mesmo dia calendário (BRT) em que
o contato foi criado como perfil no Klaviyo.

Grava na tabela leads_v2 (upsert por klaviyo_id).
"""
import sys, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import httpx
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs

from src.config import settings
from src.klaviyo.client import _extrair_utms_de_propriedades
from src.klaviyo.models import Contato, UTMs
from src.attribution.mapper import atribuir_origem
from supabase import create_client

_BRT = timezone(timedelta(hours=-3))

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
h = {
    "Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY,
    "revision": "2024-02-15",
    "accept": "application/json",
}

_TIPOS_ATIVO    = {"Active on Site"}
_TIPOS_FORM     = {"Form submitted by profile", "Form completed by profile"}
_TIPOS_LEAD_ADS = {"Filled Out Lead Ad"}


def _para_brt(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str).astimezone(_BRT)


def _data_brt(dt_str: str) -> str:
    """Retorna só a data (YYYY-MM-DD) em BRT a partir de uma string ISO."""
    return _para_brt(dt_str).strftime("%Y-%m-%d")


def _utms_diretas(props: dict) -> UTMs:
    return UTMs(
        source=props.get("utm_source"),
        medium=props.get("utm_medium"),
        campaign=props.get("utm_campaign"),
        content=props.get("utm_content"),
        term=props.get("utm_term"),
    )


def _utms_de_url(url: str) -> UTMs:
    params = parse_qs(urlparse(url).query)
    def _p(k: str) -> str | None:
        return (params.get(k) or [None])[0]
    return UTMs(
        source=_p("utm_source"), medium=_p("utm_medium"),
        campaign=_p("utm_campaign"), content=_p("utm_content"), term=_p("utm_term"),
    )


def _buscar_todos_eventos(klaviyo_id: str) -> list:
    url = "https://a.klaviyo.com/api/events/"
    params = {
        "filter": f'equals(profile_id,"{klaviyo_id}")',
        "page[size]": 50,
        "sort": "datetime",
        "fields[event]": "datetime,event_properties",
        "include": "metric",
        "fields[metric]": "name",
    }
    todos: list[dict] = []
    while url:
        r = httpx.get(url, headers=h, params=params, timeout=15)
        r.raise_for_status()
        dados = r.json()
        metricas = {m["id"]: m["attributes"]["name"] for m in dados.get("included", [])}
        for ev in dados.get("data", []):
            mid = (ev.get("relationships", {}).get("metric", {}).get("data") or {}).get("id")
            ev["_nome"] = metricas.get(mid, "")
        todos.extend(dados.get("data", []))
        url = (dados.get("links") or {}).get("next")
        params = {}
    return todos


def buscar_utms_no_dia_criacao(klaviyo_id: str, criado_em_iso: str) -> tuple[UTMs | None, str | None, str]:
    """
    Busca o evento mais antigo com UTM no mesmo dia calendário (BRT) da criação do perfil.
    Retorna (utms, url_conversao, metodo).
    """
    data_criacao_brt = _data_brt(criado_em_iso)
    eventos = _buscar_todos_eventos(klaviyo_id)

    # Filtra apenas eventos do dia de criação em BRT
    eventos_do_dia = [
        ev for ev in eventos
        if _data_brt(ev["attributes"]["datetime"]) == data_criacao_brt
    ]

    # Já chegam ordenados por datetime ASC — pega o mais antigo com UTM entre os 4 tipos

    # Prioridade 1: Active on Site
    for ev in eventos_do_dia:
        if ev["_nome"] in _TIPOS_ATIVO:
            utms = _utms_diretas(ev["attributes"].get("event_properties", {}))
            if utms.tem_dados():
                return utms, None, "ativo_no_site"

    # Prioridade 2: Formulário
    for ev in eventos_do_dia:
        if ev["_nome"] in _TIPOS_FORM:
            utms = _utms_diretas(ev["attributes"].get("event_properties", {}))
            if utms.tem_dados():
                return utms, None, "formulario"

    # Prioridade 3: Checkout com full_landing_site
    for ev in eventos_do_dia:
        props = ev["attributes"].get("event_properties", {})
        extra = props.get("$extra") or {}
        url_landing = extra.get("full_landing_site") or props.get("full_landing_site")
        if url_landing:
            utms = _utms_de_url(url_landing)
            if utms.tem_dados():
                return utms, url_landing, "checkout"

    # Prioridade 4: Lead Ads
    for ev in eventos_do_dia:
        if ev["_nome"] in _TIPOS_LEAD_ADS:
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


# --- Carrega os 50 leads da leads_v2 ---
res = db.table("leads_v2").select(
    "klaviyo_id, email, criado_em"
).execute()

leads_raw = res.data
print(f"Leads carregados da leads_v2: {len(leads_raw)}\n")
print(f"{'criado_em (BRT)':<22} {'metodo':<22} {'source':<25} {'email'}")
print("-" * 100)

registros = []
stats = {"propriedade_contato": 0, "ativo_no_site": 0, "formulario": 0,
         "checkout": 0, "lead_ads": 0, "sem_utm": 0}

for item in leads_raw:
    criado_em = item["criado_em"]
    criado_brt = _para_brt(criado_em).isoformat()

    # Recarrega propriedades do perfil via API para verificar Initial Source
    r = httpx.get(
        f"https://a.klaviyo.com/api/profiles/{item['klaviyo_id']}/",
        headers=h,
        params={"fields[profile]": "email,created,properties"},
        timeout=15,
    )
    r.raise_for_status()
    attrs = r.json()["data"]["attributes"]

    contato = Contato(
        klaviyo_id=item["klaviyo_id"],
        email=attrs.get("email"),
        criado_em=criado_brt,
        utms_propriedade=_extrair_utms_de_propriedades(attrs.get("properties", {})),
    )

    evento_utms, url_conversao, metodo_evento = None, None, "sem_utm"
    if not contato.utms_propriedade.tem_dados():
        evento_utms, url_conversao, metodo_evento = buscar_utms_no_dia_criacao(
            contato.klaviyo_id, criado_em
        )
        time.sleep(0.15)

    atribuicao = atribuir_origem(contato, evento_utms)

    if atribuicao["metodo_atribuicao"] == "evento_mais_antigo":
        atribuicao["metodo_atribuicao"] = metodo_evento

    stats[atribuicao["metodo_atribuicao"]] += 1

    source = atribuicao.get("utm_source") or "(null)"
    metodo = atribuicao["metodo_atribuicao"]
    email = (contato.email or "")[:35]
    print(f"{criado_brt[:19]:<22} {metodo:<22} {source:<25} {email}")
    if url_conversao:
        print(f"  checkout url: {url_conversao[:90]}")

    registros.append({
        "klaviyo_id": contato.klaviyo_id,
        "email": contato.email,
        "criado_em": criado_brt,
        **atribuicao,
        "url_conversao": url_conversao,
    })

db.table("leads_v2").upsert(registros, on_conflict="klaviyo_id").execute()

total = len(registros)
com_utm = total - stats["sem_utm"]
cobertura = round(com_utm / total * 100, 1)
print(f"\n{'=' * 100}")
print(f"Total:                   {total}")
print(f"Via propriedade:         {stats['propriedade_contato']}")
print(f"Via ativo no site:       {stats['ativo_no_site']}")
print(f"Via formulário:          {stats['formulario']}")
print(f"Via checkout:            {stats['checkout']}")
print(f"Via lead ads:            {stats['lead_ads']}")
print(f"Sem UTM:                 {stats['sem_utm']}")
print(f"Cobertura total:         {cobertura}%")
