"""
Extração Jun/01-10: ~19.160 leads com concorrência e checkpoint.

Arquitetura:
- 5 workers paralelos (ThreadPoolExecutor)
- Filtro de data na API do Klaviyo (só eventos do dia de criação, em BRT)
- Short-circuit: para na primeira prioridade encontrada
- Checkpoint por página em checkpoint_junho.json (retoma se interrompido)
- Batch upsert de 100 leads por vez no Supabase
"""
import sys, json, logging, threading, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from concurrent.futures import ThreadPoolExecutor, as_completed
from src.klaviyo.client import KlaviyoClient
from src.klaviyo.models import Contato
from src.attribution.mapper import atribuir_origem, extrair_utms_de_eventos, detectar_origem_invalida
from src.supabase.client import SupabaseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "checkpoint_junho.json"
START_DATE = "2026-06-01"
END_DATE   = "2026-06-10"
MAX_WORKERS = 5

klaviyo = KlaviyoClient()
db = SupabaseClient()


def _carregar_checkpoint() -> str | None:
    try:
        with open(CHECKPOINT_FILE) as f:
            data = json.load(f)
            if data.get("concluido"):
                logger.info("Extração já concluída. Apague %s para re-executar.", CHECKPOINT_FILE)
                sys.exit(0)
            return data.get("cursor")
    except FileNotFoundError:
        return None


def _salvar_checkpoint(cursor: str | None) -> None:
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"cursor": cursor, "concluido": cursor is None}, f)


def _processar_lead(contato: Contato) -> dict:
    invalida = detectar_origem_invalida(contato.email, contato.properties)
    if invalida:
        utms, metodo = invalida
        url_conversao = None
    else:
        eventos = klaviyo.buscar_eventos_no_dia(contato.klaviyo_id, contato.criado_em)
        utms, url_conversao, metodo = extrair_utms_de_eventos(eventos)

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


def _coletar_resultados(
    executor: ThreadPoolExecutor, perfis: list[Contato]
) -> tuple[list[dict], int]:
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
    eta_min = (19160 - total) / lpm if lpm > 0 else 0
    logger.info(
        "Página %d | %d leads | %.0f leads/min | cobertura %s%% | ETA ~%.0f min",
        pagina, total, lpm, cobertura, eta_min,
    )


def main() -> None:
    cursor = _carregar_checkpoint()
    if cursor:
        logger.info("Retomando do checkpoint...")
    else:
        logger.info("Iniciando extração %s → %s com %d workers", START_DATE, END_DATE, MAX_WORKERS)

    total = sem_utm_total = pagina = 0
    inicio = time.monotonic()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for perfis, proximo_cursor in klaviyo.paginar_contatos(START_DATE, END_DATE, cursor):
            pagina += 1
            batch, sem_utm_pagina = _coletar_resultados(executor, perfis)
            db.upsert_leads_batch(batch)
            _salvar_checkpoint(proximo_cursor)
            total += len(batch)
            sem_utm_total += sem_utm_pagina
            _log_progresso(pagina, total, sem_utm_total, inicio)

    cobertura = round((1 - sem_utm_total / total) * 100, 1) if total else 0
    logger.info("Concluído. Total: %d | Cobertura: %.1f%%", total, cobertura)


if __name__ == "__main__":
    main()
