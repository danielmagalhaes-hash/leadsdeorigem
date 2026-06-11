"""
Diagnóstico: data de criação do perfil vs data do primeiro evento com UTM.

Para cada um dos 50 leads da leads_v2, busca no Klaviyo o evento mais antigo
com UTM e compara com o criado_em do perfil.

Objetivo: detectar se algum evento ocorreu ANTES da criação do perfil
(evidência de backfill de visitante anônimo) ou quantos dias depois.
"""
import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import httpx
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs

from src.config import settings
from supabase import create_client

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

h = {
    "Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY,
    "revision": "2024-02-15",
    "accept": "application/json",
}

_TIPOS_ATIVO    = {"Active on Site"}
_TIPOS_FORM     = {"Form submitted by profile", "Form completed by profile"}
_TIPOS_LEAD_ADS = {"Filled Out Lead Ad"}
_TIPOS_CHECKOUT = {"Checkout started", "Started Checkout"}


def _para_dt(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str).astimezone(timezone.utc)


def _tem_utm(props: dict) -> bool:
    for k in ("utm_source", "utm_medium", "utm_campaign"):
        v = props.get(k)
        if v and isinstance(v, str):
            try:
                float(v)
            except ValueError:
                return True
    return False


def _utm_de_url(url: str) -> bool:
    params = parse_qs(urlparse(url).query)
    return any(params.get(k) for k in ("utm_source", "utm_medium", "utm_campaign"))


def buscar_primeiro_evento_com_utm(klaviyo_id: str) -> tuple[str | None, str | None]:
    """
    Retorna (datetime_iso, tipo_evento) do evento mais antigo com UTM.
    Percorre todos os eventos em ordem cronológica crescente.
    """
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

    todos.sort(key=lambda e: e.get("attributes", {}).get("datetime", ""))

    for ev in todos:
        nome = ev.get("_nome", "")
        props = ev.get("attributes", {}).get("event_properties", {})
        dt = ev.get("attributes", {}).get("datetime")

        if nome in _TIPOS_ATIVO | _TIPOS_FORM | _TIPOS_LEAD_ADS:
            if _tem_utm(props):
                return dt, nome

        if nome in _TIPOS_CHECKOUT:
            extra = props.get("$extra") or {}
            url_landing = extra.get("full_landing_site") or props.get("full_landing_site")
            if url_landing and _utm_de_url(url_landing):
                return dt, nome

    return None, None


# --- Carrega os 50 leads da leads_v2 ---
res = db.table("leads_v2").select(
    "klaviyo_id, email, criado_em, metodo_atribuicao, origem, utm_source"
).execute()

leads = res.data
print(f"Leads carregados da leads_v2: {len(leads)}\n")
print(f"{'criado_em':<22} {'primeiro_evento_em':<22} {'delta':<12} {'metodo':<22} {'tipo_evento':<30} {'email'}")
print("-" * 130)

antes = 0
mesmo_dia = 0
depois = 0
sem_evento = 0

for lead in leads:
    criado = _para_dt(lead["criado_em"])
    metodo = lead["metodo_atribuicao"]
    email = (lead.get("email") or "")[:35]

    ev_dt_str, ev_tipo = buscar_primeiro_evento_com_utm(lead["klaviyo_id"])
    time.sleep(0.1)

    if not ev_dt_str:
        sem_evento += 1
        print(
            f"{lead['criado_em'][:19]:<22} {'(sem evento UTM)':<22} {'—':<12} {metodo:<22} {'—':<30} {email}"
        )
        continue

    ev_dt = _para_dt(ev_dt_str)
    delta = ev_dt - criado
    dias = delta.days
    horas = delta.total_seconds() / 3600

    if dias < 0:
        label = f"{abs(dias)}d ANTES"
        antes += 1
    elif dias == 0:
        label = f"{int(horas)}h depois"
        mesmo_dia += 1
    else:
        label = f"{dias}d depois"
        depois += 1

    print(
        f"{lead['criado_em'][:19]:<22} {ev_dt_str[:19]:<22} {label:<12} {metodo:<22} {(ev_tipo or ''):<30} {email}"
    )

total = len(leads)
print(f"\n{'=' * 130}")
print(f"Total analisado:          {total}")
print(f"Evento ANTES da criação:  {antes}  {'← backfill detectado' if antes > 0 else ''}")
print(f"Evento no mesmo dia:      {mesmo_dia}")
print(f"Evento DEPOIS da criação: {depois}")
print(f"Sem evento com UTM:       {sem_evento}")
