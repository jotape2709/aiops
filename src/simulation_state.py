from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from src.chart_data import short_link_label
from src.incident_engine import Incident, correlate, generate_alerts
from src.models import INFO_LABEL, SEVERITY_LABELS_PT, Scenario
from src.synthetic_data import Sample, generate_sample


@dataclass(frozen=True)
class SimulationEvent:
    event_id: str
    incident_id: str
    timestamp: datetime
    host: str
    severity: str
    status: str
    description: str
    service: str


@dataclass(frozen=True)
class SimulationState:
    sample: Sample
    active_incidents: tuple[Incident, ...]
    history: tuple[SimulationEvent, ...]
    started_at: datetime
    clock: Callable[[], datetime]


def _incidents(sample: Sample) -> tuple[Incident, ...]:
    alerts = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
    return correlate(alerts, sample)


def initial_state(
    seed: int,
    variant: int = 0,
    started_at: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SimulationState:
    start = started_at or datetime.now().astimezone().replace(microsecond=0)
    event_clock = clock or (
        lambda: start if started_at is not None else datetime.now().astimezone()
    )
    return SimulationState(
        generate_sample(seed, Scenario.NORMAL, variant), (), (), start, event_clock
    )


def _resolve_active(state: SimulationState) -> tuple[SimulationEvent, ...]:
    active_ids = {incident.id for incident in state.active_incidents}
    return tuple(
        replace(event, status="Resolvido")
        if event.incident_id in active_ids and event.status == "Ativo"
        else event
        for event in state.history
    )


def _next_timestamp(state: SimulationState, history: tuple[SimulationEvent, ...]) -> datetime:
    return history[-1].timestamp + timedelta(seconds=1) if history else state.clock()


def _event_id(history: tuple[SimulationEvent, ...], offset: int = 0) -> str:
    return f"EVT-{len(history) + offset + 1:06d}"


def _description(target: Incident | str) -> str:
    cause = target.cause if isinstance(target, Incident) else target
    if "--" in cause:
        if isinstance(target, Incident) and any(
            alert.metric == "status" and alert.value == "DOWN" for alert in target.alerts
        ):
            return "Link indisponível"
        if "SW-ACCESS" in cause:
            return "Link indisponível"
        return "Link degradado"
    if cause.startswith("SRV-"):
        return "CPU elevada"
    return "Equipamento indisponível"


def simulate(
    state: SimulationState, scenario: Scenario, *, reapplied_after_seed: bool = False
) -> SimulationState:
    sample = generate_sample(state.sample.seed, scenario, state.sample.variant)
    incidents = _incidents(sample)
    history = _resolve_active(state)
    first_timestamp = _next_timestamp(state, history)
    new_events = tuple(
        SimulationEvent(
            event_id=_event_id(history, index),
            incident_id=incident.id,
            timestamp=first_timestamp + timedelta(seconds=index),
            host=(
                short_link_label(*incident.cause.split("--", 1))
                if "--" in incident.cause
                else incident.cause
            ),
            severity=SEVERITY_LABELS_PT[incident.severity],
            status="Ativo",
            description=(
                f"{_description(incident)} (reaplicado após troca de seed)"
                if reapplied_after_seed
                else _description(incident)
            ),
            service=", ".join(incident.affected_services) if incident.affected_services else "—",
        )
        for index, incident in enumerate(incidents)
    )
    return SimulationState(sample, incidents, history + new_events, state.started_at, state.clock)


def restore(state: SimulationState) -> SimulationState:
    if state.sample.scenario == Scenario.NORMAL and not state.active_incidents:
        return state
    sample = generate_sample(state.sample.seed, Scenario.NORMAL, state.sample.variant)
    history = _resolve_active(state)
    event = SimulationEvent(
        event_id=_event_id(history),
        incident_id="",
        timestamp=_next_timestamp(state, history),
        host="AMBIENTE",
        severity=INFO_LABEL,
        status="Resolvido",
        description="Recuperação do ambiente",
        service="—",
    )
    return SimulationState(sample, (), history + (event,), state.started_at, state.clock)


def change_seed(state: SimulationState, seed: int) -> SimulationState:
    """Preserva eventos, resolve o incidente anterior e reaplica o cenário ativo.

    A variante é intencionalmente reiniciada em 0 (a UI zera sample_index na troca de seed
    para permitir comparação determinística do cenário com a mesma base amostral).
    """
    base = SimulationState(
        generate_sample(seed), (), _resolve_active(state), state.started_at, state.clock
    )
    return (
        simulate(base, state.sample.scenario, reapplied_after_seed=True)
        if state.sample.scenario != Scenario.NORMAL
        else base
    )


def resample(state: SimulationState, variant: int) -> SimulationState:
    sample = generate_sample(state.sample.seed, state.sample.scenario, variant)
    return SimulationState(sample, _incidents(sample), state.history, state.started_at, state.clock)
