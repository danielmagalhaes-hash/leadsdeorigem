from typing import Any
from src.klaviyo.models import Contato, UTMs
from src.attribution.rules import _mapear


def atribuir_origem(contato: Contato, evento_mais_antigo_utms: UTMs | None = None) -> dict[str, Any]:
    if contato.utms_propriedade.tem_dados():
        utms = contato.utms_propriedade
        metodo = "propriedade_contato"
    elif evento_mais_antigo_utms and evento_mais_antigo_utms.tem_dados():
        utms = evento_mais_antigo_utms
        metodo = "evento_mais_antigo"
    else:
        utms = UTMs()
        metodo = "sem_utm"

    origem = _mapear(utms.source, utms.medium, utms.campaign)

    return {
        "origem": origem,
        "metodo_atribuicao": metodo,
        "utm_source": utms.source,
        "utm_medium": utms.medium,
        "utm_campaign": utms.campaign,
        "utm_content": utms.content,
        "utm_term": utms.term,
    }
