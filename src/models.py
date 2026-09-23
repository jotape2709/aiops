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


class Severity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class Scenario(str, Enum):
    NORMAL = "normal"
    CORE_SWITCH_DOWN = "core_switch_down"


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
