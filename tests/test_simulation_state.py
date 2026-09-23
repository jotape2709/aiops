from src.models import Scenario
from src.simulation_state import change_seed, initial_state, resample, restore, simulate


def test_recovery_resolves_incident_and_preserves_history() -> None:
    state = initial_state(42)
    active = simulate(state, Scenario.CORE_SWITCH_DOWN)
    assert len(active.active_incidents) == 1
    assert len(active.history) == 1
    assert active.history[0].status == "Ativo"
    recovered = restore(active)
    assert recovered.sample.scenario == Scenario.NORMAL
    assert not recovered.active_incidents
    assert len(recovered.history) == 1
    assert recovered.history[0].status == "Resolvido"
    assert initial_state(43).history == ()


def test_variant_survives_scenario_change_and_resampling() -> None:
    state = resample(initial_state(42), 3)
    active = simulate(state, Scenario.LINK_DOWN)
    assert active.sample.variant == 3
    assert active.sample.seed == 42
    assert restore(active).sample.variant == 3
    assert len(active.history) == 1


def test_seed_change_reapplies_active_scenario_and_preserves_history() -> None:
    active = simulate(initial_state(42), Scenario.LINK_DOWN)
    changed = change_seed(active, 43)
    assert changed.sample.seed == 43
    assert changed.sample.scenario == Scenario.LINK_DOWN
    assert changed.sample.variant == 0
    assert len(changed.active_incidents) == 1
    assert len(changed.history) == 2
    assert changed.history[0].status == "Resolvido"
    assert changed.history[1].status == "Ativo"
