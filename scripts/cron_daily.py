"""
Cron diário: captura leads criados ontem e grava na leads_v2.
Rodar todos os dias às 02h via Task Scheduler (Windows) ou cron (Linux/Mac).

Uso: python scripts/cron_daily.py
     python scripts/cron_daily.py --data 2026-06-15   # forçar data específica
"""
import sys, logging, time, argparse
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.klaviyo.client import KlaviyoClient
from src.klaviyo.models import Contato
from src.attribution.mapper import atribuir_origem, extrair_utms_de_eventos, detectar_origem_invalida, tem_evento_de_atribuicao
from src.supabase.client import SupabaseClient

MAX_WORKERS = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

klaviyo = KlaviyoClient()
db = SupabaseClient()


def _parse_args() -> tuple[str, str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", help="Data a extrair (YYYY-MM-DD). Padrão: ontem.")
    args = parser.parse_args()
    if args.data:
        target = date.fromisoformat(args.data)
    else:
        target = date.today() - timedelta(days=1)
    return target.isoformat(), (target + timedelta(days=1)).isoformat()


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


def main() -> None:
    start_date, end_date = _parse_args()
    logger.info("Cron diário: extraindo leads de %s", start_date)

    total = sem_utm_total = 0
    inicio = time.monotonic()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for perfis, _ in klaviyo.paginar_contatos(start_date, end_date, None):
            batch, sem_utm_pagina = _coletar_resultados(executor, perfis)
            if batch:
                db.upsert_leads_batch(batch)
            total += len(batch)
            sem_utm_total += sem_utm_pagina

    elapsed = round((time.monotonic() - inicio) / 60, 1)
    cobertura = round((1 - sem_utm_total / total) * 100, 1) if total else 0
    logger.info(
        "Concluído. Data: %s | Total: %d | Cobertura bruta: %.1f%% | Tempo: %.1f min",
        start_date, total, cobertura, elapsed,
    )


if __name__ == "__main__":
    main()
