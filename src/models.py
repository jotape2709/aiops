from dataclasses import dataclass
from enum import Enum


class NodeType(str, Enum):
    INTERNET = "internet"
    ROUTER = "router"
    FIREWALL = "firewall"
    CORE_SWITCH = "core_switch"
    ACCESS_SWITCH = "access_switch"
    SERVER = "server"
    SERVICE = "service"


class Status(str, Enum):
    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"


STATUS_LABELS_PT: dict[Status, str] = {
    Status.UP: "Operacional",
    Status.DEGRADED: "Degradado",
    Status.DOWN: "Indisponível",
}
IMPACTED_LABEL: str = "Impactado"


class Severity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


SEVERITY_LABELS_PT: dict[Severity, str] = {
    Severity.CRITICAL: "Crítico",
    Severity.WARNING: "Aviso",
}
INFO_LABEL: str = "Informativo"


class Scenario(str, Enum):
    NORMAL = "normal"
    LINK_DEGRADED = "link_degraded"
    LINK_DOWN = "link_down"
    CORE_SWITCH_DOWN = "core_switch_down"
    CPU_HIGH = "cpu_high"


@dataclass(frozen=True)
class Node:
    id: str
    hostname: str
    type: NodeType
    status: Status
    site: str
    ip: str | None
    cpu: float | None
    memory: float | None
    latency: float | None
    packet_loss: float | None
    availability: float | None


@dataclass(frozen=True)
class Link:
    source: str
    target: str
    status: Status
    utilization: float
    latency: float
    capacity_mbps: int
    packet_loss: float = 0.0
