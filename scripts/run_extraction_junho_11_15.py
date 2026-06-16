"""
Extração Jun/11-15: gap entre extração de junho e início do cron.
~9.500 leads estimados. Sem checkpoint (pequeno o suficiente para rodar de uma vez).
"""
import sys, json, logging, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from concurrent.futures import ThreadPoolExecutor, as_completed
from src.klaviyo.client import KlaviyoClient
from src.klaviyo.models import Contato
from src.attribution.mapper import atribuir_origem, extrair_utms_de_eventos, detectar_origem_invalida, tem_evento_de_atribuicao
from src.supabase.client import SupabaseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

START_DATE  = "2026-06-11"
END_DATE    = "2026-06-15"
MAX_WORKERS = 10
TOTAL_ESTIMADO = 9_500

klaviyo = KlaviyoClient()
db = SupabaseClient()


def _processar_lead(contato: Contato) -> dict:
    invalida = detectar_origem_invalida(contato.email, contato.properties)
    if invalida and invalida[1] == "integracao_tiktok":
        utms, metodo = invalida
        url_conversao = None
    else:
        eventos = klaviyo.buscar_eventos_no_dia(contato.klaviyo_id, contato.criado_em)
        utms, url_conversao, metodo = extrair_utms_de_eventos(eventos)
        if invalida and metodo == "sem_utm" and not tem_evento_de_atribuicao(eventos):
            utms, metodo = invalida

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


def _coletar_resultados(executor: ThreadPoolExecutor, perfis: list[Contato]) -> tuple[list[dict], int]:
    futures = {executor.submit(_processar_lead, p): p for p in perfis}
    batch: list[dict] = []
    sem_utm = 0
    for future in as_completed(futures):
        try:
            resultado = future.result()
            batch.append(resultado)
            if resultado["metodo_atribuicao"] == "sem_utm":
                sem_utm += 1
        except Exception:
            contato = futures[future]
            logger.error("Falha ao processar %s", contato.klaviyo_id, exc_info=True)
    return batch, sem_utm


def _log_progresso(pagina: int, total: int, sem_utm: int, inicio: float) -> None:
    elapsed = time.monotonic() - inicio
    lpm = total / (elapsed / 60) if elapsed > 0 else 0
    cobertura = round((1 - sem_utm / total) * 100, 1) if total else 0
    eta_min = (TOTAL_ESTIMADO - total) / lpm if lpm > 0 else 0
    logger.info(
        "Página %d | %d leads | %.0f leads/min | cobertura bruta %s%% | ETA ~%.0f min",
        pagina, total, lpm, cobertura, eta_min,
    )


def main() -> None:
    logger.info("Iniciando extração %s → %s com %d workers", START_DATE, END_DATE, MAX_WORKERS)
    total = sem_utm_total = pagina = 0
    inicio = time.monotonic()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for perfis, _ in klaviyo.paginar_contatos(START_DATE, END_DATE, None):
            pagina += 1
            batch, sem_utm_pagina = _coletar_resultados(executor, perfis)
            if batch:
                db.upsert_leads_batch(batch)
            total += len(batch)
            sem_utm_total += sem_utm_pagina
            _log_progresso(pagina, total, sem_utm_total, inicio)

    cobertura = round((1 - sem_utm_total / total) * 100, 1) if total else 0
    logger.info("Concluído. Total: %d | Cobertura bruta: %.1f%%", total, cobertura)


if __name__ == "__main__":
    main()
