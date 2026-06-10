"""
Extrai 50 leads recentes com pipeline completo:
1. Verifica propriedades do contato (utm_source, Initial Source, etc.)
2. Se não encontrar, busca eventos (Active on Site, Form submitted)
Grava no Supabase e exibe cobertura.
"""
import sys, time
sys.path.insert(0, ".")
from src.config import settings
from src.klaviyo.client import KlaviyoClient
from src.attribution.mapper import atribuir_origem
from supabase import create_client
import httpx

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
h = {"Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY, "revision": "2024-02-15"}

# Busca 50 leads recentes
r = httpx.get(
    "https://a.klaviyo.com/api/profiles/",
    headers=h,
    params={
        "filter": "greater-than(created,2026-06-07T00:00:00+00:00)",
        "page[size]": 50,
        "fields[profile]": "email,created,properties",
    },
    timeout=30
)

from src.klaviyo.models import Contato, UTMs

leads_raw = r.json().get("data", [])
print(f"Leads retornados: {len(leads_raw)}\n")

klaviyo = KlaviyoClient()
registros = []
stats = {"propriedade_contato": 0, "evento_mais_antigo": 0, "sem_utm": 0}

for item in leads_raw:
    attrs = item.get("attributes", {})
    props = attrs.get("properties", {})

    # Monta contato com propriedades
    from src.klaviyo.client import _extrair_utms_de_propriedades
    contato = Contato(
        klaviyo_id=item["id"],
        email=attrs.get("email"),
        criado_em=attrs.get("created"),
        utms_propriedade=_extrair_utms_de_propriedades(props),
    )

    # Busca evento se não tem propriedade
    evento_utms = None
    if not contato.utms_propriedade.tem_dados():
        evento_utms = klaviyo.buscar_evento_mais_antigo_com_utm(contato.klaviyo_id)
        time.sleep(0.1)  # respeita rate limit

    atribuicao = atribuir_origem(contato, evento_utms)
    stats[atribuicao["metodo_atribuicao"]] += 1

    lead = {
        "klaviyo_id": contato.klaviyo_id,
        "email": contato.email,
        "criado_em": contato.criado_em,
        **atribuicao,
    }
    registros.append(lead)

    metodo = atribuicao["metodo_atribuicao"]
    source = atribuicao.get("utm_source") or "(null)"
    print(f"{contato.criado_em[:10]} | {metodo:<22} | source: {source}")

# Grava no Supabase
db.table("leads").upsert(registros, on_conflict="klaviyo_id").execute()

total = len(registros)
cobertura = round((stats["propriedade_contato"] + stats["evento_mais_antigo"]) / total * 100, 1)

print(f"\n=== RESUMO ===")
print(f"Total:                   {total}")
print(f"Via propriedade:         {stats['propriedade_contato']}")
print(f"Via evento (fallback):   {stats['evento_mais_antigo']}")
print(f"Sem UTM:                 {stats['sem_utm']}")
print(f"Cobertura total:         {cobertura}%")
