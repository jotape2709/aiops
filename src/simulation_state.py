from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from src.incident_engine import Incident, correlate, generate_alerts
from src.models import Scenario
from src.synthetic_data import Sample, generate_sample


@dataclass(frozen=True)
class SimulationEvent:
    incident_id: str
    timestamp: datetime
    host: str
    category: str
    severity: str
    status: str
    description: str
    service: str


@dataclass(frozen=True)
class SimulationState:
    sample: Sample
    active_incidents: tuple[Incident, ...]
    history: tuple[SimulationEvent, ...]


def _incidents(sample: Sample) -> tuple[Incident, ...]:
    alerts = generate_alerts(sample.nodes, sample.links, sample.cpu_series)
    return correlate(alerts, sample)


def initial_state(seed: int, variant: int = 0) -> SimulationState:
    return SimulationState(generate_sample(seed, Scenario.NORMAL, variant), (), ())


def _resolve_active(state: SimulationState) -> tuple[SimulationEvent, ...]:
    active_ids = {incident.id for incident in state.active_incidents}
    return tuple(
        replace(event, status="Resolvido")
        if event.incident_id in active_ids and event.status == "Ativo"
        else event
        for event in state.history
    )


def simulate(state: SimulationState, scenario: Scenario) -> SimulationState:
    sample = generate_sample(state.sample.seed, scenario, state.sample.variant)
    incidents = _incidents(sample)
    history = _resolve_active(state)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    new_events = tuple(
        SimulationEvent(
            incident_id=incident.id,
            timestamp=base_time + timedelta(minutes=len(history) + index),
            host=incident.cause,
            category="Incidente sintético",
            severity=incident.severity.value,
            status="Ativo",
            description=f"Anomalia em {incident.cause}.",
            service=", ".join(incident.affected_services),
        )
        for index, incident in enumerate(incidents)
    )
    return SimulationState(sample, incidents, history + new_events)


def restore(state: SimulationState) -> SimulationState:
    sample = generate_sample(state.sample.seed, Scenario.NORMAL, state.sample.variant)
    return SimulationState(sample, (), _resolve_active(state))


def change_seed(state: SimulationState, seed: int) -> SimulationState:
    """Preserva eventos, resolve o incidente anterior e reaplica o cenário ativo."""
    base = SimulationState(generate_sample(seed), (), _resolve_active(state))
    return (
        simulate(base, state.sample.scenario) if state.sample.scenario != Scenario.NORMAL else base
    )


def resample(state: SimulationState, variant: int) -> SimulationState:
    sample = generate_sample(state.sample.seed, state.sample.scenario, variant)
    return SimulationState(sample, _incidents(sample), state.history)
