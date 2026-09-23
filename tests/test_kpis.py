from src.kpis import compute_kpis
from src.models import Scenario
from src.synthetic_data import generate_sample


def test_normal_kpis() -> None:
    sample = generate_sample(42)
    kpis = compute_kpis(sample)
    assert kpis.availability == 100.0
    assert kpis.active_alerts == 0
    assert kpis.critical_incidents == 0
    assert kpis.impacted_services == 0
    assert abs(kpis.mean_latency - sum(sample.latency_series) / 60) < 0.001


def test_core_down_kpis() -> None:
    sample = generate_sample(42, Scenario.CORE_SWITCH_DOWN)
    kpis = compute_kpis(sample)
    assert kpis.availability < 100.0
    assert kpis.critical_incidents == 1
    assert kpis.impacted_services == 3
    assert kpis.mean_latency > compute_kpis(generate_sample(42)).mean_latency
