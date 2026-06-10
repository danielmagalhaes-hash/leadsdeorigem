from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UTMs:
    source: Optional[str] = None
    medium: Optional[str] = None
    campaign: Optional[str] = None
    content: Optional[str] = None
    term: Optional[str] = None

    def tem_dados(self) -> bool:
        # Ignora valores numéricos — são IDs internos do Klaviyo ($source: -9, -127), não UTMs reais
        def _valido(v: Optional[str]) -> bool:
            if not v:
                return False
            try:
                float(str(v))
                return False  # é número → ID interno, ignorar
            except ValueError:
                return True
        return any(_valido(v) for v in [self.source, self.medium, self.campaign])


@dataclass
class Contato:
    klaviyo_id: str
    email: Optional[str]
    criado_em: str
    utms_propriedade: UTMs = field(default_factory=UTMs)


@dataclass
class Evento:
    klaviyo_id: str
    tipo: str
    ocorrido_em: str
    utms: UTMs = field(default_factory=UTMs)
