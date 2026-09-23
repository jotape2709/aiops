from src.chart_data import short_link_label
from src.simulation_state import SimulationEvent

EVENT_COLUMNS = (
    "ID do evento",
    "Horário",
    "Host",
    "Severidade",
    "Status",
    "Descrição",
    "Serviço afetado",
)


def _format_host(host: str) -> str:
    if "--" in host:
        source, target = host.split("--", 1)
        return short_link_label(source, target)
    return host


def event_rows(history: tuple[SimulationEvent, ...]) -> tuple[dict[str, str], ...]:
    """Prepara eventos recentes em ordem decrescente para a tabela da UI."""
    ordered = sorted(history, key=lambda event: (event.timestamp, event.event_id), reverse=True)
    return tuple(
        {
            "ID do evento": event.event_id,
            "Horário": event.timestamp.strftime("%d/%m %H:%M:%S"),
            "Host": _format_host(event.host),
            "Severidade": event.severity,
            "Status": event.status,
            "Descrição": event.description,
            "Serviço afetado": event.service if event.service else "—",
        }
        for event in ordered
    )
