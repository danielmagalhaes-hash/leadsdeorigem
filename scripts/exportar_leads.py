"""
Exporta toda a tabela leads_v2 para CSV.
Uso: python scripts/exportar_leads.py
Gera: exports/leads_v2_YYYY-MM-DD.csv
"""
import sys, csv, os
from datetime import date
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from supabase import create_client
from src.config import settings

COLUNAS = [
    "klaviyo_id", "email", "criado_em", "origem",
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "url_conversao", "metodo_atribuicao", "processado_em",
]

os.makedirs("exports", exist_ok=True)
arquivo = f"exports/leads_v2_{date.today()}.csv"

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

total = 0
offset = 0
PAGE = 1000

with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=COLUNAS, extrasaction="ignore")
    writer.writeheader()

    while True:
        rows = (
            db.table("leads_v2")
            .select(", ".join(COLUNAS))
            .order("criado_em")
            .range(offset, offset + PAGE - 1)
            .execute()
            .data
        )
        if not rows:
            break
        writer.writerows(rows)
        total += len(rows)
        print(f"  {total} leads exportados...", end="\r")
        if len(rows) < PAGE:
            break
        offset += PAGE

print(f"\nConcluído. {total} leads → {arquivo}")
