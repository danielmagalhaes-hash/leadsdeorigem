import sys, httpx, json
sys.path.insert(0, ".")
from src.config import settings

h = {"Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY, "revision": "2024-02-15"}
profile_id = "01KT07SV9FTKNS1S5F43CMA8J3"

r = httpx.get("https://a.klaviyo.com/api/events/", headers=h,
    params={
        "filter": f'equals(profile_id,"{profile_id}")',
        "sort": "datetime",
        "page[size]": 5,
        "fields[event]": "datetime,event_properties",
    }, timeout=10)

print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json().get("data", [])
    print(f"Eventos encontrados: {len(data)}")
    for ev in data:
        attrs = ev.get("attributes", {})
        props = attrs.get("event_properties", {})
        utms = {k: v for k, v in props.items() if "utm" in str(k).lower()}
        print(f"  {attrs.get('datetime')} | utms: {utms}")
        if not utms:
            print(f"  (sem UTM) keys disponíveis: {list(props.keys())[:8]}")
else:
    print(r.text[:400])
