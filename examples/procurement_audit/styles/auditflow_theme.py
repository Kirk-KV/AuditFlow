from pathlib import Path

import plotly.io as pio
import yaml

from html import escape


def render_metadata_card(fields: dict, title: str | None = None) -> str:
    title_html = ""

    if title:
        title_html = f'<div class="audit-meta-title">{escape(str(title))}</div>'

    rows = []

    for key, value in fields.items():
        rows.append(
            f"<dt>{escape(str(key))}</dt>"
            f"<dd>{escape('' if value is None else str(value))}</dd>"
        )

    rows_html = "\n".join(rows)

    return f"""
            <div class="audit-meta">
            {title_html}
            <dl>
            {rows_html}
            </dl>
            </div>
            """

def load_brand_config(project_root: Path | str) -> dict:
    project_root = Path(project_root)
    brand_path = project_root / "styles" / "brand.yml"

    with brand_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def get_chart_palette(project_root: Path | str) -> list[str]:
    config = load_brand_config(project_root)
    return config["chart_palette"]


def get_brand_colors(project_root: Path | str) -> dict:
    config = load_brand_config(project_root)
    return config["colors"]


def apply_auditflow_plotly_theme(project_root: Path | str) -> None:
    """
    Apply the AuditFlow Plotly theme globally.

    Use this once at the beginning of a QMD document.
    """
    config = load_brand_config(project_root)
    colors = config["colors"]
    palette = config["chart_palette"]

    template = pio.templates["plotly_white"]

    template.layout.colorway = palette
    template.layout.font = {
        "family": "Arial, sans-serif",
        "color": colors["text"],
        "size": 13,
    }
    template.layout.title = {
        "font": {
            "size": 18,
            "color": colors["primary"],
        }
    }
    template.layout.paper_bgcolor = colors["background"]
    template.layout.plot_bgcolor = colors["background"]

    template.layout.xaxis = {
        "gridcolor": colors["border"],
        "linecolor": colors["border"],
        "zerolinecolor": colors["border"],
    }
    template.layout.yaxis = {
        "gridcolor": colors["border"],
        "linecolor": colors["border"],
        "zerolinecolor": colors["border"],
    }

    pio.templates["auditflow"] = template
    pio.templates.default = "auditflow"