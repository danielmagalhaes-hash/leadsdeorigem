import logging
from src.config import settings
from src.klaviyo.client import KlaviyoClient
from src.attribution.mapper import atribuir_origem
from src.supabase.client import SupabaseClient

logger = logging.getLogger(__name__)


def executar_extracao() -> None:
    klaviyo = KlaviyoClient()
    db = SupabaseClient()

    start = settings.EXTRACTION_START_DATE
    end = settings.EXTRACTION_END_DATE
    logger.info("Iniciando extração: %s → %s", start, end)

    total = 0
    sem_utm = 0

    for contato in klaviyo.listar_contatos(start, end):
        evento_utms = None
        if not contato.utms_propriedade.tem_dados():
            evento_utms = klaviyo.buscar_evento_mais_antigo_com_utm(contato.klaviyo_id)

        atribuicao = atribuir_origem(contato, evento_utms)

        lead = {
            "klaviyo_id": contato.klaviyo_id,
            "email": contato.email,
            "criado_em": contato.criado_em,
            **atribuicao,
        }

        db.upsert_lead(lead)
        total += 1

        if atribuicao["metodo_atribuicao"] == "sem_utm":
            sem_utm += 1

        if total % 50 == 0:
            cobertura = round((1 - sem_utm / total) * 100, 1)
            logger.info("Processados: %d | Cobertura UTM: %s%%", total, cobertura)

    cobertura_final = round((1 - sem_utm / total) * 100, 1) if total else 0
    logger.info("Extração concluída. Total: %d | Cobertura UTM: %s%%", total, cobertura_final)
