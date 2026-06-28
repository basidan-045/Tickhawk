# =============================================================================
# grapher.py — Generates an interactive Plotly line chart of all tick data.
#
# WHY Plotly instead of matplotlib? Matplotlib renders every data point as a
# static image. At 100k+ ticks it becomes extremely slow and the resulting
# PNG is unreadable at normal zoom. Plotly renders in the browser using
# WebGL, handles 500k+ points smoothly, and supports pan/zoom/hover natively.
# =============================================================================

import logging
import webbrowser
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go

import config
from data_store import TickStore

logger = logging.getLogger(__name__)


def _build_output_path(symbol: str, date_str: str) -> Path:
    """
    Build the full output file path for the HTML chart.

    Args:
        symbol:   Stock symbol, e.g. "RELIANCE".
        date_str: Date string in DD-MM-YYYY format.

    Returns:
        Path object for the .html output file.
    """
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{symbol.upper()}_{date_str}.html"
    return output_dir / filename


def generate_chart(
    store: TickStore,
    symbol: str,
    open_in_browser: bool = True,
) -> Path:
    """
    Generate a Plotly interactive line chart from tick data and save as HTML.

    The chart shows every single tick as a data point connected by a line.
    Users can zoom, pan, and hover to see exact time and price for any point.

    Args:
        store:           TickStore instance to read from.
        symbol:          Stock symbol for chart title and filename.
        open_in_browser: If True, opens the HTML file in the default browser.

    Returns:
        Path to the written .html file.
    """
    ticks = store.get_all_ticks()
    date_str = datetime.now().strftime("%d-%m-%Y")
    output_path = _build_output_path(symbol, date_str)

    if not ticks:
        logger.warning("No ticks to chart — skipping graph generation.")
        return output_path

    times = [t["time"] for t in ticks]
    prices = [t["price"] for t in ticks]

    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(  # Scattergl uses WebGL — handles 500k+ points
            x=times,
            y=prices,
            mode="lines",
            name=symbol.upper(),
            line=dict(color="#1F4E79", width=1),
            hovertemplate=(
                "<b>Time:</b> %{x}<br>"
                "<b>Price:</b> ₹%{y:,.2f}<br>"
                "<extra></extra>"  # Removes the default trace name box
            ),
        )
    )

    # ── Layout ───────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=f"{symbol.upper()} — Tick-by-Tick Price | {date_str}",
            font=dict(size=20),
            x=0.5,
        ),
        xaxis=dict(
            title="Time (IST)",
            tickangle=-45,
            rangeslider=dict(visible=True),   # Minimap at bottom for navigation
            type="category",                   # Treat time as category to avoid
                                               # gaps during pre/post-market silence
        ),
        yaxis=dict(
            title="Price (₹)",
            tickformat=",.2f",
            side="left",
        ),
        hovermode="x unified",   # Show all series values at the same x position
        plot_bgcolor="#F8F9FA",
        paper_bgcolor="#FFFFFF",
        font=dict(family="Arial", size=12),
        margin=dict(l=60, r=40, t=80, b=80),
        height=650,
    )

    # ── Annotation: total ticks ───────────────────────────────────────────
    fig.add_annotation(
        text=f"Total ticks: {len(ticks):,}",
        xref="paper", yref="paper",
        x=1.0, y=1.02,
        showarrow=False,
        font=dict(size=11, color="#666666"),
    )

    fig.write_html(
        str(output_path),
        include_plotlyjs="cdn",    # Load Plotly from CDN — keeps file small
        full_html=True,
    )
    logger.info(f"Chart saved: {output_path} ({len(ticks):,} data points)")
    print(f"[SAVED] Chart → {output_path} ({len(ticks):,} ticks)")

    if open_in_browser:
        webbrowser.open(output_path.resolve().as_uri())
        print("[INFO] Chart opened in browser.")

    return output_path
