"""
Corrige leads já gravados na leads_v2 que são TikTok Shop ou HubSpot.
Rodar APÓS a extração principal terminar.
"""
import sys, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

import httpx
from src.config import settings
from src.attribution.mapper import detectar_origem_invalida, atribuir_origem
from src.klaviyo.models import Contato, UTMs
from supabase import create_client

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
h = {
    "Authorization": "Klaviyo-API-Key " + settings.KLAVIYO_API_KEY,
    "revision": "2024-02-15",
    "accept": "application/json",
}

# --- 1. TikTok Shop: detecção por email, sem precisar chamar Klaviyo ---
res_tiktok = db.table("leads_v2").update({
    "utm_source": "tik tok shop",
    "metodo_atribuicao": "integracao_tiktok",
    "origem": "Inválido",
}).like("email", "%@tiktokshop.com.br").execute()
print(f"TikTok Shop corrigidos: {len(res_tiktok.data)}")

# --- 2. HubSpot: busca perfis sem_utm e verifica hs_object_source_label ---
# Pagina o Supabase de 1000 em 1000 (limite padrão da API)
leads_sem_utm = []
offset = 0
while True:
    chunk = db.table("leads_v2").select("klaviyo_id, email, criado_em").eq(
        "metodo_atribuicao", "sem_utm"
    ).range(offset, offset + 999).execute().data
    leads_sem_utm.extend(chunk)
    if len(chunk) < 1000:
        break
    offset += 1000
print(f"\nLeads sem_utm para verificar: {len(leads_sem_utm)}")

corrigidos = 0
em_lote = []

for lead in leads_sem_utm:
    r = httpx.get(
        f"https://a.klaviyo.com/api/profiles/{lead['klaviyo_id']}/",
        headers=h,
        params={"fields[profile]": "email,properties"},
        timeout=15,
    )
    r.raise_for_status()
    attrs = r.json()["data"]["attributes"]
    props = attrs.get("properties", {})
    time.sleep(0.05)

    invalida = detectar_origem_invalida(lead.get("email"), props)
    if not invalida:
        continue

    utms, metodo = invalida
    contato = Contato(klaviyo_id=lead["klaviyo_id"], email=lead.get("email"),
                      criado_em=lead["criado_em"])
    atribuicao = atribuir_origem(contato, utms)
    atribuicao["metodo_atribuicao"] = metodo

    em_lote.append({
        "klaviyo_id": lead["klaviyo_id"],
        "email": lead.get("email"),
        "criado_em": lead["criado_em"],
        **atribuicao,
        "url_conversao": None,
    })

    if len(em_lote) >= 100:
        db.table("leads_v2").upsert(em_lote, on_conflict="klaviyo_id").execute()
        corrigidos += len(em_lote)
        print(f"  Corrigidos até agora: {corrigidos}")
        em_lote = []

if em_lote:
    db.table("leads_v2").upsert(em_lote, on_conflict="klaviyo_id").execute()
    corrigidos += len(em_lote)

print(f"\nHubSpot corrigidos: {corrigidos}")
print("Cleanup concluído.")
