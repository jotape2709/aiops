from datetime import UTC, datetime, timedelta

from src.chart_data import short_link_label, short_node_id
from src.event_data import EVENT_COLUMNS, event_rows
from src.models import Scenario
from src.simulation_state import SimulationEvent, change_seed, initial_state, restore, simulate


def test_event_table_contract_columns_order_and_types() -> None:
    assert EVENT_COLUMNS == (
        "ID do evento",
        "Horário",
        "Host",
        "Severidade",
        "Status",
        "Descrição",
        "Serviço afetado",
    )
    start = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
    state = initial_state(42, started_at=start)
    assert event_rows(state.history) == ()

    state = simulate(state, Scenario.LINK_DEGRADED)
    state = simulate(state, Scenario.LINK_DOWN)
    rows = event_rows(state.history)
    assert len(rows) == 2
    assert tuple(rows[0]) == EVENT_COLUMNS
    assert tuple(rows[1]) == EVENT_COLUMNS

    # Ordem decrescente (mais recente primeiro)
    assert rows[0]["ID do evento"] == "EVT-000002"
    assert rows[1]["ID do evento"] == "EVT-000001"
    assert rows[0]["Horário"] == "23/09 12:00:01"
    assert rows[1]["Horário"] == "23/09 12:00:00"

    # Severidade em português e sem emojis
    assert rows[0]["Severidade"] == "Crítico"
    assert rows[1]["Severidade"] == "Aviso"
    for row in rows:
        assert row["Severidade"] in {"Crítico", "Aviso", "Informativo"}
        assert not any(char in row["Severidade"] for char in ("🔴", "🟠", "🔵", "🟢"))

    # Status
    assert rows[0]["Status"] == "Ativo"
    assert rows[1]["Status"] == "Resolvido"

    # Host de link encurtado
    assert rows[0]["Host"] == "CORE → ACC1"
    assert rows[1]["Host"] == "EDGE1 → FW"

    # Descrição sem repetir o host
    assert rows[0]["Descrição"] == "Link indisponível"
    assert rows[1]["Descrição"] == "Link degradado"
    assert "CORE" not in rows[0]["Descrição"]
    assert "EDGE1" not in rows[1]["Descrição"]


def test_anomaly_descriptions_by_type_without_host() -> None:
    start = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
    state = initial_state(42, started_at=start)

    # Core switch down -> Equipamento indisponível
    core_state = simulate(state, Scenario.CORE_SWITCH_DOWN)
    core_rows = event_rows(core_state.history)
    assert core_rows[0]["Descrição"] == "Equipamento indisponível"
    assert core_rows[0]["Host"] == "SW-CORE-01"

    # CPU alta -> CPU elevada
    cpu_state = simulate(state, Scenario.CPU_HIGH)
    cpu_rows = event_rows(cpu_state.history)
    assert cpu_rows[0]["Descrição"] == "CPU elevada"
    assert cpu_rows[0]["Host"] == "SRV-API-01"


def test_recovery_and_seed_reapply_contract() -> None:
    start = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
    active = simulate(initial_state(42, started_at=start), Scenario.CPU_HIGH)

    # Troca de seed: reaplicado com sufixo
    changed = change_seed(active, 43)
    assert [event.timestamp for event in changed.history] == [start, start + timedelta(seconds=1)]
    assert changed.history[0].status == "Resolvido"
    assert changed.history[1].status == "Ativo"
    assert changed.history[1].description == "CPU elevada (reaplicado após troca de seed)"

    changed_rows = event_rows(changed.history)
    assert changed_rows[0]["Descrição"] == "CPU elevada (reaplicado após troca de seed)"

    # Recuperação do ambiente
    recovered = restore(changed)
    assert recovered.history[1].status == "Resolvido"
    recovery = recovered.history[2]
    assert recovery.event_id == "EVT-000003"
    assert recovery.severity == "Informativo"
    assert recovery.status == "Resolvido"
    assert recovery.timestamp == start + timedelta(seconds=2)
    assert recovery.description == "Recuperação do ambiente"
    assert recovery.service == "—"

    recovered_rows = event_rows(recovered.history)
    assert recovered_rows[0]["Descrição"] == "Recuperação do ambiente"
    assert recovered_rows[0]["Serviço afetado"] == "—"
    assert recovered_rows[0]["Severidade"] == "Informativo"


def test_short_link_formatting_in_event_rows() -> None:
    # Evento construído com host longo em formato link
    event = SimulationEvent(
        event_id="EVT-000099",
        incident_id="INC-1",
        timestamp=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        host="RTR-EDGE-01--FW-CORE-01",
        severity="Aviso",
        status="Ativo",
        description="Link degradado",
        service="",
    )
    rows = event_rows((event,))
    assert rows[0]["Host"] == "EDGE1 → FW"
    assert rows[0]["Serviço afetado"] == "—"
    assert short_node_id("RTR-EDGE-01") == "EDGE1"
    assert short_link_label("RTR-EDGE-01", "FW-CORE-01") == "EDGE1 → FW"
