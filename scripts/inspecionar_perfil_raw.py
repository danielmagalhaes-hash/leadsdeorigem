import sys, httpx
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from src.config import settings

EMAIL = "liviamtanure@gmail.com"
API_KEY = settings.KLAVIYO_API_KEY
headers = {
    "Authorization": f"Klaviyo-API-Key {API_KEY}",
    "revision": "2024-02-15",
    "accept": "application/json",
}

r = httpx.get(
    "https://a.klaviyo.com/api/profiles/",
    headers=headers,
    params={
        "filter": f'equals(email,"{EMAIL}")',
    },
    timeout=15,
)
r.raise_for_status()
profiles = r.json()["data"]

if not profiles:
    print("Perfil não encontrado")
else:
    p = profiles[0]
    print("id:", p["id"])
    print("locale:", p["attributes"].get("locale"))
    print("location:", p["attributes"].get("location"))
    print("$source:", p["attributes"].get("properties", {}).get("$source"))
    print()
    print("=== TODOS OS ATTRIBUTES ===")
    for k, v in p["attributes"].items():
        print(f"  {k}: {v}")
