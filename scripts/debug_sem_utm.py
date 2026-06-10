"""
Mostra eventos com nome (via include=metric) para rfm2807 e tarcisobarcelos26.
"""
import sys, httpx
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from src.config import settings

h = {"Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY,
     "revision": "2024-02-15", "accept": "application/json"}

for email in ["rfm2807@gmail.com", "tarcisobarcelos26@gmail.com"]:
    r = httpx.get("https://a.klaviyo.com/api/profiles/", headers=h,
        params={"filter": f'equals(email,"{email}")', "fields[profile]": "email"}, timeout=15)
    kid = r.json()["data"][0]["id"]

    r2 = httpx.get("https://a.klaviyo.com/api/events/", headers=h,
        params={"filter": f'equals(profile_id,"{kid}")', "page[size]": 10,
                "fields[event]": "datetime,event_properties",
                "include": "metric", "fields[metric]": "name"}, timeout=15)
    dados = r2.json()
    metricas = {m["id"]: m["attributes"]["name"] for m in dados.get("included", [])}
    eventos = sorted(dados.get("data", []), key=lambda e: e["attributes"].get("datetime", ""))

    print(f"=== {email} ===")
    for ev in eventos:
        metric_id = (ev.get("relationships", {}).get("metric", {}).get("data") or {}).get("id")
        nome = metricas.get(metric_id, "?")
        dt = ev["attributes"].get("datetime", "")[:19]
        props = ev["attributes"].get("event_properties", {})
        print(f"  {dt} | {nome}")
        for k in ["utm_source", "Platform", "CampaignName", "AdName", "AdsetName", "method", "list_name"]:
            if k in props:
                print(f"    {k}: {props[k]}")
    print()
