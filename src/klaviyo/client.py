import time
import logging
from datetime import datetime, timezone, timedelta
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


_BRT = timezone(timedelta(hours=-3))


def _range_utc_do_dia_brt(criado_em_utc: str) -> tuple[str, str]:
    """Converte criado_em (UTC ISO) para o intervalo UTC equivalente ao dia BRT."""
    fmt = "%Y-%m-%dT%H:%M:%S+00:00"
    dt_brt = datetime.fromisoformat(criado_em_utc).astimezone(_BRT)
    inicio = datetime(dt_brt.year, dt_brt.month, dt_brt.day, tzinfo=_BRT).astimezone(timezone.utc)
    fim = inicio + timedelta(days=1)
    return inicio.strftime(fmt), fim.strftime(fmt)


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

    def buscar_eventos_no_dia(self, klaviyo_id: str, criado_em_utc: str) -> list[dict]:
        """Busca eventos do perfil filtrados ao dia BRT de criação, ordenados por datetime ASC."""
        inicio, fim = _range_utc_do_dia_brt(criado_em_utc)
        url = f"{_BASE}/events/"
        params: dict = {
            "filter": f'equals(profile_id,"{klaviyo_id}"),greater-than(datetime,{inicio}),less-than(datetime,{fim})',
            "sort": "datetime",
            "page[size]": 50,
            "fields[event]": "datetime,event_properties",
            "include": "metric",
            "fields[metric]": "name",
        }
        eventos: list[dict] = []
        while url:
            dados = _get(url, params)
            metricas = {m["id"]: m["attributes"]["name"] for m in dados.get("included", [])}
            for ev in dados.get("data", []):
                mid = (ev.get("relationships", {}).get("metric", {}).get("data") or {}).get("id")
                ev["_nome"] = metricas.get(mid, "")
            eventos.extend(dados.get("data", []))
            url = (dados.get("links") or {}).get("next")
            params = {}
        return eventos

    def paginar_contatos(
        self, start_date: str, end_date: str, cursor_url: str | None = None
    ) -> Generator[tuple[list[Contato], str | None], None, None]:
        """Yields (lista_perfis, proximo_cursor) página por página. Suporta resume via cursor_url."""
        from datetime import date as _date
        fim = _date.fromisoformat(end_date) + timedelta(days=1)
        url: str | None = cursor_url or f"{_BASE}/profiles/"
        params: dict = {} if cursor_url else {
            "filter": f"greater-than(created,{start_date}T03:00:00+00:00),less-than(created,{fim.isoformat()}T03:00:00+00:00)",
            "page[size]": _PAGE_SIZE,
            "fields[profile]": "email,created,properties",
        }
        while url:
            dados = _get(url, params)
            perfis = [
                Contato(
                    klaviyo_id=item["id"],
                    email=item["attributes"].get("email"),
                    criado_em=item["attributes"].get("created"),
                    utms_propriedade=UTMs(),
                    properties=item["attributes"].get("properties", {}),
                )
                for item in dados.get("data", [])
            ]
            next_url: str | None = (dados.get("links") or {}).get("next")
            yield perfis, next_url
            url = next_url
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
