import logging
from typing import Any
from supabase import create_client, Client
from src.config import settings

logger = logging.getLogger(__name__)

_supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY,
)


class SupabaseClient:

    def upsert_lead(self, lead: dict[str, Any]) -> None:
        _supabase.table("leads").upsert(lead, on_conflict="klaviyo_id").execute()
        logger.debug("Lead gravado: %s | origem: %s", lead["klaviyo_id"], lead["origem"])

    def upsert_leads_batch(self, leads: list[dict[str, Any]]) -> None:
        _supabase.table("leads_v2").upsert(leads, on_conflict="klaviyo_id").execute()
        logger.debug("Batch gravado: %d leads", len(leads))

    def contar_leads(self) -> int:
        resultado = _supabase.table("leads").select("id", count="exact").execute()
        return resultado.count or 0
