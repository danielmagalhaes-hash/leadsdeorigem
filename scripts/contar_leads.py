"""
Conta leads criados no período para estimar volume e tempo de extração.
"""
import sys, httpx, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from src.config import settings

h = {"Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY,
     "revision": "2024-02-15", "accept": "application/json"}

START = "2026-04-22"  # greater-than, então pega a partir de 23/04
END   = "2026-06-11"  # less-than, então pega até 10/06

url = "https://a.klaviyo.com/api/profiles/"
params = {
    "filter": f"greater-than(created,{START}T00:00:00+00:00),less-than(created,{END}T00:00:00+00:00)",
    "page[size]": 100,
    "fields[profile]": "created",
}

total = 0
paginas = 0
primeira_data = None
ultima_data = None

while url:
    r = httpx.get(url, headers=h, params=params, timeout=30)
    if r.status_code == 429:
        time.sleep(2)
        continue
    r.raise_for_status()
    dados = r.json()
    items = dados.get("data", [])
    total += len(items)
    paginas += 1

    if items:
        if not primeira_data:
            ultima_data = items[0]["attributes"]["created"][:10]
        primeira_data = items[-1]["attributes"]["created"][:10]

    print(f"  Página {paginas}: {len(items)} leads | acumulado: {total}", end="\r")
    url = (dados.get("links") or {}).get("next")
    params = {}

print(f"\n\nTotal de leads ({START} → {END}): {total}")
print(f"Período: {primeira_data} até {ultima_data}")
print(f"Páginas paginadas: {paginas}")

# Estimativa de tempo
seg_por_lead = 1.5  # eventos API call + include=metric + 0.1s sleep
total_segundos = total * seg_por_lead
print(f"\nEstimativa de tempo:")
print(f"  ~{seg_por_lead}s por lead × {total} leads = {total_segundos:.0f}s")
print(f"  = {total_segundos/60:.0f} minutos (~{total_segundos/3600:.1f}h)")
