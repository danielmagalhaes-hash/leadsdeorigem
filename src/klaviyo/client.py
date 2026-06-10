import time
import logging
from typing import Generator
import httpx
from src.config import settings
from src.klaviyo.models import Contato, Evento, UTMs

logger = logging.getLogger(__name__)

_BASE = "https://a.klaviyo.com/api"
_HEADERS = {
    "Authorization": f"Klaviyo-API-Key {settings.KLAVIYO_API_KEY}",
    "revision": "2024-02-15",
    "accept": "application/json",
}
_MAX_RETRIES = 5
_PAGE_SIZE = 100


def _get(url: str, params: dict) -> dict:
    for tentativa in range(_MAX_RETRIES):
        try:
            response = httpx.get(url, headers=_HEADERS, params=params, timeout=30)
            if response.status_code == 429:
                espera = 2 ** tentativa
                logger.warning("Rate limit atingido. Aguardando %ds", espera)
                time.sleep(espera)
                continue
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Erro HTTP %s em %s", e.response.status_code, url)
            raise
    raise RuntimeError(f"Rate limit persistente após {_MAX_RETRIES} tentativas: {url}")


def _extrair_utms_de_propriedades(props: dict) -> UTMs:
    # Prioridade: campos "Initial Source" do Klaviyo (How did they find you?) → utm_* padrão
    # Ignora $source pois armazena nomes de flow/form internos, não UTMs reais
    return UTMs(
        source=props.get("Initial Source") or props.get("utm_source"),
        medium=props.get("Initial Source Medium") or props.get("utm_medium"),
        campaign=props.get("Initial Source Campaign") or props.get("utm_campaign"),
        content=props.get("Initial Source Content") or props.get("utm_content"),
        term=props.get("Initial Source Term") or props.get("utm_term"),
    )


def _extrair_utms_de_metadata(meta: dict) -> UTMs:
    return UTMs(
        source=meta.get("utm_source"),
        medium=meta.get("utm_medium"),
        campaign=meta.get("utm_campaign"),
        content=meta.get("utm_content"),
        term=meta.get("utm_term"),
    )


class KlaviyoClient:

    def listar_contatos(self, start_date: str, end_date: str) -> Generator[Contato, None, None]:
        # Klaviyo só suporta greater-than e less-than (sem igual)
        # Ajuste: subtrair 1s no início e adicionar 1 dia no fim para cobrir o intervalo completo
        from datetime import date, timedelta
        fim = date.fromisoformat(end_date) + timedelta(days=1)

        url = f"{_BASE}/profiles/"
        params = {
            "filter": f"greater-than(created,{start_date}T00:00:00+00:00),less-than(created,{fim.isoformat()}T00:00:00+00:00)",
            "page[size]": _PAGE_SIZE,
            "fields[profile]": "email,created,properties",
        }

        while url:
            dados = _get(url, params)
            for item in dados.get("data", []):
                attrs = item.get("attributes", {})
                props = attrs.get("properties", {})
                yield Contato(
                    klaviyo_id=item["id"],
                    email=attrs.get("email"),
                    criado_em=attrs.get("created"),
                    utms_propriedade=_extrair_utms_de_propriedades(props),
                )
            url = (dados.get("links") or {}).get("next")
            params = {}

    def buscar_evento_mais_antigo_com_utm(self, klaviyo_id: str) -> UTMs | None:
        url = f"{_BASE}/events/"
        params = {
            "filter": f'equals(profile_id,"{klaviyo_id}")',
            "sort": "datetime",
            "page[size]": 50,
            "fields[event]": "datetime,event_properties",
        }

        dados = _get(url, params)
        for item in dados.get("data", []):
            props = item.get("attributes", {}).get("event_properties", {})
            utms = _extrair_utms_de_metadata(props)
            if utms.tem_dados():
                logger.debug("UTM encontrado em evento para %s", klaviyo_id)
                return utms

        return None
