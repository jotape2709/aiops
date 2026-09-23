import pandas as pd
import streamlit as st

from src.event_data import EVENT_COLUMNS
from src.models import INFO_LABEL, SEVERITY_LABELS_PT, Severity

SEVERITY_ICONS = {
    SEVERITY_LABELS_PT[Severity.CRITICAL]: "🔴",
    SEVERITY_LABELS_PT[Severity.WARNING]: "🟠",
    INFO_LABEL: "🔵",
}

_MIN_WIDTH = 96
_MAX_WIDTH = 420
_CHAR_PX = 7.4
_PAD_PX = 18


def severity_badge(value: str) -> str:
    icon = SEVERITY_ICONS.get(value)
    return f"{icon} {value}" if icon else value


def _display_rows(
    rows: tuple[dict[str, str], ...], columns: tuple[str, ...]
) -> tuple[dict[str, str], ...]:
    if "Severidade" not in columns:
        return rows
    return tuple({**row, "Severidade": severity_badge(row.get("Severidade", ""))} for row in rows)


def _column_widths(rows: tuple[dict[str, str], ...], columns: tuple[str, ...]) -> dict[str, int]:
    widths: dict[str, int] = {}
    for column in columns:
        longest = max((len(str(row.get(column, ""))) for row in rows), default=0)
        longest = max(longest, len(column))
        widths[column] = min(_MAX_WIDTH, max(_MIN_WIDTH, round(longest * _CHAR_PX) + _PAD_PX))
    return widths


def render_event_table(rows: tuple[dict[str, str], ...]) -> None:
    """Renderiza eventos com colunas e configuração derivadas de EVENT_COLUMNS."""
    if not rows:
        st.info("Nenhum evento recente.")
        return
    display = _display_rows(rows, EVENT_COLUMNS)
    st.dataframe(
        pd.DataFrame(display, columns=list(EVENT_COLUMNS)),
        hide_index=True,
        width="stretch",
        column_config={
            column: st.column_config.TextColumn(column, width=width)
            for column, width in _column_widths(display, EVENT_COLUMNS).items()
        },
    )
