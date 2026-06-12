"""
Re-processa leads com metodo_atribuicao='integracao_hubspot' com a nova regra:
  - tem qualquer um dos 4 eventos (mesmo sem UTM) → Direto
  - não tem nenhum dos 4 eventos → mantém integracao_hubspot
"""
import sys, logging, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client
from src.config import settings
from src.klaviyo.client import KlaviyoClient
from src.klaviyo.models import Contato, UTMs
from src.attribution.mapper import atribuir_origem, extrair_utms_de_eventos, tem_evento_de_atribuicao

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

MAX_WORKERS = 5
BATCH_SIZE = 100

klaviyo = KlaviyoClient()
_supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

_HUBSPOT_UTMS = UTMs(source="lead criado no hubspot antigo")


def _buscar_leads_hubspot() -> list[dict]:
    todos: list[dict] = []
    PAGE = 1000
    offset = 0
    while True:
        resultado = (
            _supabase.table("leads_v2")
            .select("klaviyo_id,email,criado_em")
            .eq("metodo_atribuicao", "integracao_hubspot")
            .range(offset, offset + PAGE - 1)
            .execute()
        )
        pagina = resultado.data
        todos.extend(pagina)
        if len(pagina) < PAGE:
            break
        offset += PAGE
    return todos


def _reprocessar(row: dict) -> dict:
    contato = Contato(
        klaviyo_id=row["klaviyo_id"],
        email=row["email"],
        criado_em=row["criado_em"],
    )
    eventos = klaviyo.buscar_eventos_no_dia(contato.klaviyo_id, contato.criado_em)
    utms, url_conversao, metodo = extrair_utms_de_eventos(eventos)

    if metodo == "sem_utm" and not tem_evento_de_atribuicao(eventos):
        utms, metodo = _HUBSPOT_UTMS, "integracao_hubspot"

    atribuicao = atribuir_origem(contato, utms)
    if atribuicao["metodo_atribuicao"] == "evento_mais_antigo":
        atribuicao["metodo_atribuicao"] = metodo

    return {
        "klaviyo_id": contato.klaviyo_id,
        "email": contato.email,
        "criado_em": contato.criado_em,
        **atribuicao,
        "url_conversao": url_conversao,
    }


def main() -> None:
    leads = _buscar_leads_hubspot()
    total = len(leads)
    logger.info("Leads HubSpot a re-processar: %d", total)

    processados = direto = manteve_hubspot = com_utm = 0
    inicio = time.monotonic()
    batch: list[dict] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_reprocessar, row): row for row in leads}
        for future in as_completed(futures):
            try:
                resultado = future.result()
                batch.append(resultado)
                processados += 1

                m = resultado["metodo_atribuicao"]
                if m == "integracao_hubspot":
                    manteve_hubspot += 1
                elif resultado["origem"] == "Direto" and m == "sem_utm":
                    direto += 1
                else:
                    com_utm += 1

                if len(batch) >= BATCH_SIZE:
                    _supabase.table("leads_v2").upsert(batch, on_conflict="klaviyo_id").execute()
                    batch = []

                if processados % 500 == 0:
                    elapsed = time.monotonic() - inicio
                    lpm = processados / (elapsed / 60)
                    eta = (total - processados) / lpm if lpm > 0 else 0
                    logger.info(
                        "%d/%d | %.0f leads/min | Direto: %d | HubSpot: %d | UTM: %d | ETA ~%.0f min",
                        processados, total, lpm, direto, manteve_hubspot, com_utm, eta,
                    )
            except Exception:
                logger.error("Falha em %s", futures[future]["klaviyo_id"], exc_info=True)

    if batch:
        _supabase.table("leads_v2").upsert(batch, on_conflict="klaviyo_id").execute()

    logger.info(
        "Concluído. Total: %d | → Direto: %d | → Manteve HubSpot: %d | → Outro (com UTM): %d",
        processados, direto, manteve_hubspot, com_utm,
    )


if __name__ == "__main__":
    main()
