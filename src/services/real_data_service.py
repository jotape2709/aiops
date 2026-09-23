from dataclasses import dataclass
from enum import Enum


class RealDataState(str, Enum):
    NOT_CONFIGURED = "nao_configurado"


@dataclass(frozen=True)
class RealDataStatus:
    state: RealDataState
    message: str


def get_real_data_status() -> RealDataStatus:
    return RealDataStatus(RealDataState.NOT_CONFIGURED, "Dados reais não configurados no M1.")
