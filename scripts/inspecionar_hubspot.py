import sys; sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
import httpx
from src.config import settings

h = {
    "Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY,
    "revision": "2024-02-15",
    "accept": "application/json",
}

emails = ["jsemedohi@gmail.com", "fabricio_13@hotmail.com", "rossipin@gmail.com"]

for email in emails:
    r = httpx.get("https://a.klaviyo.com/api/profiles/",
        headers=h,
        params={"filter": f'equals(email,"{email}")', "fields[profile]": "email,created,properties"},
        timeout=15)
    data = r.json().get("data", [])
    if not data:
        print(f"{email}: NAO ENCONTRADO")
        continue
    profile = data[0]
    print(f"\n=== {email} ===")
    print(f"klaviyo_id : {profile['id']}")
    print(f"created    : {profile['attributes']['created']}")
    print("properties :")
    for k, v in sorted(profile["attributes"].get("properties", {}).items()):
        print(f"  {k}: {v}")

    # Eventos do perfil
    pid = profile["id"]
    re = httpx.get("https://a.klaviyo.com/api/events/",
        headers=h,
        params={"filter": f'equals(profile_id,"{pid}")',
                "sort": "datetime", "page[size]": 5,
                "fields[event]": "datetime", "include": "metric", "fields[metric]": "name"},
        timeout=15)
    eventos = re.json()
    metricas = {m["id"]: m["attributes"]["name"] for m in eventos.get("included", [])}
    evs = eventos.get("data", [])
    print(f"eventos ({len(evs)} mais antigos):")
    for ev in evs:
        mid = (ev.get("relationships", {}).get("metric", {}).get("data") or {}).get("id")
        nome = metricas.get(mid, "?")
        print(f"  {ev['attributes']['datetime']} | {nome}")
