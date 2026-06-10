"""
Testa múltiplas formas de buscar eventos e campos do contato.
"""
import sys, httpx
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from src.config import settings

PROFILE_ID = "01KTFRGD39E2NFBBR50NPZ0S9E"  # liviamtanure@gmail.com
h = {"Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY, "revision": "2024-02-15"}

# Teste 1: eventos sem sort e sem filtro de fields
print("=== TESTE 1: eventos sem sort ===")
r = httpx.get("https://a.klaviyo.com/api/events/", headers=h,
    params={"filter": f'equals(profile_id,"{PROFILE_ID}")', "page[size]": 10},
    timeout=15)
print(f"Status: {r.status_code}")
dados = r.json()
eventos = dados.get("data", [])
print(f"Eventos retornados: {len(eventos)}")
if eventos:
    for ev in eventos[:3]:
        a = ev["attributes"]
        print(f"  {a.get('datetime','')[:19]} | {a.get('event_name','?')}")
        print(f"  Keys em event_properties: {list(a.get('event_properties',{}).keys())[:10]}")
print()

# Teste 2: campos adicionais do profile (predictive_analytics)
print("=== TESTE 2: additional-fields no profile ===")
r2 = httpx.get(f"https://a.klaviyo.com/api/profiles/{PROFILE_ID}", headers=h,
    params={"additional-fields[profile]": "predictive_analytics"},
    timeout=15)
attrs2 = r2.json()["data"]["attributes"]
if "predictive_analytics" in attrs2:
    print(f"predictive_analytics: {attrs2['predictive_analytics']}")
else:
    print("Sem predictive_analytics")
    print(f"Chaves retornadas: {list(attrs2.keys())}")
