from src.ui.cards import kpi_card_html


def test_kpi_card_html_renders_optional_hint() -> None:
    without_hint = kpi_card_html("Alertas ativos", "0")
    assert "noc-hint" not in without_hint
    with_hint = kpi_card_html("Disponibilidade", "100.0%", "equipamentos alcançáveis")
    assert '<div class="noc-hint">equipamentos alcançáveis</div>' in with_hint


def test_kpi_card_html_escapes_labels_and_values() -> None:
    html = kpi_card_html("<script>", "1 < 2")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "1 &lt; 2" in html
