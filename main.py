# =============================================================================
# main.py — Entry point. Wires all modules together.
#
# Execution flow:
#   1. Validate config
#   2. Resolve instrument token
#   3. Login to Angel One
#   4. Wait for market open (9:15 AM IST)
#   5. Start websocket + auto-save thread
#   6. Run until 3:30 PM IST
#   7. Final save + generate chart
# =============================================================================

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, time as dtime
from pathlib import Path

import pytz
import schedule

import config
from auth import login
from data_store import TickStore
from exporter import export_to_excel
from grapher import generate_chart
from instrument import resolve_symbol_to_token
from websocket_client import TickWebSocket

# ── Logging Setup ─────────────────────────────────────────────────────────────
# Log to both console (INFO) and a daily error file (WARNING+)
IST = pytz.timezone("Asia/Kolkata")
today_str = datetime.now(IST).strftime("%d-%m-%Y")
log_filename = f"errors_{today_str}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── Global state ─────────────────────────────────────────────────────────────
store = TickStore()
ws_client: TickWebSocket | None = None
shutdown_event = threading.Event()


def on_tick(price: float, total_count: int) -> None:
    """
    Callback fired after every tick is stored.

    Prints to console and logs milestone counts.

    Args:
        price:       Last traded price in INR.
        total_count: Total ticks captured so far today.
    """
    now_ist = datetime.now(IST)
    time_str = now_ist.strftime("%H:%M:%S.") + f"{now_ist.microsecond // 1000:03d}"
    print(
        f"{time_str} | {config.STOCK_SYMBOL.upper()} | "
        f"₹{price:>10,.2f} | Ticks today: {total_count:,}"
    )

    # Print milestone every 100 ticks
    if total_count % 100 == 0:
        print(f"\n{'─'*60}")
        print(f"  MILESTONE: {total_count:,} ticks captured")
        print(f"{'─'*60}\n")


def autosave_job() -> None:
    """
    Scheduled job: export current ticks to Excel as a backup.
    Runs every AUTOSAVE_INTERVAL_MINUTES minutes.
    """
    if store.is_empty():
        logger.info("Auto-save skipped — no ticks yet.")
        return
    export_to_excel(store, config.STOCK_SYMBOL)


def run_scheduler() -> None:
    """
    Run the schedule loop in a background thread.
    Checks for pending jobs every 30 seconds.
    """
    while not shutdown_event.is_set():
        schedule.run_pending()
        time.sleep(30)


def wait_for_market_open() -> None:
    """
    Block until market open time (9:15 AM IST).
    Prints a countdown every 60 seconds if waiting.
    """
    open_time = dtime(config.MARKET_OPEN_HOUR, config.MARKET_OPEN_MINUTE)
    while True:
        now = datetime.now(IST).time()
        if now >= open_time:
            break
        now_dt = datetime.now(IST)
        open_dt = now_dt.replace(
            hour=config.MARKET_OPEN_HOUR,
            minute=config.MARKET_OPEN_MINUTE,
            second=0,
            microsecond=0,
        )
        seconds_left = int((open_dt - now_dt).total_seconds())
        if seconds_left > 0:
            print(f"[WAITING] Market opens in {seconds_left // 60}m {seconds_left % 60}s...")
        time.sleep(60)

    print(f"\n[MARKET OPEN] Starting tick capture for {config.STOCK_SYMBOL.upper()}...")


def is_market_closed() -> bool:
    """
    Check if current IST time is past market close (3:30 PM).

    Returns:
        True if market has closed for the day.
    """
    close_time = dtime(config.MARKET_CLOSE_HOUR, config.MARKET_CLOSE_MINUTE)
    return datetime.now(IST).time() >= close_time


def market_close_monitor() -> None:
    """
    Monitor thread: triggers shutdown at 3:30 PM IST.
    Checks every 10 seconds to stay responsive.
    """
    while not shutdown_event.is_set():
        if is_market_closed():
            print(f"\n[3:30 PM] Market closed. Finalizing...")
            logger.info("Market close reached — initiating shutdown.")
            initiate_shutdown()
            break
        time.sleep(10)


def initiate_shutdown() -> None:
    """
    Cleanly shut down: disconnect websocket, save Excel, generate chart.
    Safe to call multiple times (idempotent via shutdown_event).
    """
    if shutdown_event.is_set():
        return  # Already shutting down

    shutdown_event.set()

    # Disconnect websocket first — stops new ticks arriving during save
    if ws_client:
        ws_client.disconnect()

    tick_count = store.tick_count()
    print(f"\n{'='*60}")
    print(f"  SESSION COMPLETE | {config.STOCK_SYMBOL.upper()}")
    print(f"  Total ticks captured: {tick_count:,}")
    print(f"{'='*60}\n")

    if tick_count == 0:
        print("[WARNING] No ticks were captured. Check your token and exchange config.")
        return

    # Final Excel export
    print("[EXPORT] Writing final Excel file...")
    export_to_excel(store, config.STOCK_SYMBOL)

    # Generate interactive chart and open in browser
    print("[CHART] Generating Plotly chart...")
    generate_chart(store, config.STOCK_SYMBOL, open_in_browser=True)

    print("\n[DONE] All files saved. Check the 'output/' folder.")


def handle_signal(signum, frame) -> None:
    """
    Handle keyboard interrupt (Ctrl+C) or SIGTERM gracefully.
    Always saves data before exiting — never lose ticks.
    """
    print(f"\n[INTERRUPTED] Caught signal {signum}. Saving data before exit...")
    logger.warning(f"Signal {signum} received — initiating graceful shutdown.")
    initiate_shutdown()
    sys.exit(0)


def validate_config() -> None:
    """
    Check that all required config values are filled in before connecting.

    Raises:
        SystemExit: If any config value is a placeholder.
    """
    placeholders = {
        "API_KEY": config.API_KEY,
        "CLIENT_ID": config.CLIENT_ID,
        "PASSWORD": config.PASSWORD,
        "TOTP_SECRET": config.TOTP_SECRET,
    }
    missing = [k for k, v in placeholders.items() if "YOUR_" in str(v)]
    if missing:
        print("\n[CONFIG ERROR] Fill in these values in config.py before running:")
        for key in missing:
            print(f"  → {key}")
        sys.exit(1)


def print_banner() -> None:
    """Print startup banner with session info."""
    now = datetime.now(IST).strftime("%d %b %Y, %H:%M:%S IST")
    print("\n" + "=" * 60)
    print("  TICKHAWK — Angel One Tick Capture System")
    print("=" * 60)
    print(f"  Stock    : {config.STOCK_SYMBOL.upper()} ({config.EXCHANGE})")
    print(f"  Session  : {config.MARKET_OPEN_HOUR:02d}:{config.MARKET_OPEN_MINUTE:02d}"
          f" — {config.MARKET_CLOSE_HOUR:02d}:{config.MARKET_CLOSE_MINUTE:02d} IST")
    print(f"  Started  : {now}")
    print(f"  Auto-save: every {config.AUTOSAVE_INTERVAL_MINUTES} minutes")
    print(f"  Output   : {Path(config.OUTPUT_DIR).resolve()}")
    print("=" * 60 + "\n")


def main() -> None:
    """
    Main entry point. Orchestrates the full session lifecycle.
    """
    global ws_client

    # Register signal handlers for graceful exit on Ctrl+C
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print_banner()
    validate_config()

    # ── Step 1: Resolve instrument token ─────────────────────────────────────
    print(f"[INIT] Looking up instrument token for {config.STOCK_SYMBOL}...")
    try:
        token = resolve_symbol_to_token(config.STOCK_SYMBOL, config.EXCHANGE)
        print(f"[INIT] Token resolved: {token}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    # ── Step 2: Login ─────────────────────────────────────────────────────────
    print("[INIT] Authenticating with Angel One...")
    try:
        session = login()
        print(f"[INIT] Logged in as {session.client_id}")
    except Exception as e:
        print(f"\n[ERROR] Login failed: {e}")
        sys.exit(1)

    # ── Step 3: Wait for market open ─────────────────────────────────────────
    if is_market_closed():
        print("[INFO] Market is already closed for today. Nothing to capture.")
        sys.exit(0)

    wait_for_market_open()

    # ── Step 4: Start auto-save scheduler ────────────────────────────────────
    schedule.every(config.AUTOSAVE_INTERVAL_MINUTES).minutes.do(autosave_job)
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info(f"Auto-save scheduled every {config.AUTOSAVE_INTERVAL_MINUTES} minutes.")

    # ── Step 5: Start market close monitor ───────────────────────────────────
    close_monitor_thread = threading.Thread(target=market_close_monitor, daemon=True)
    close_monitor_thread.start()

    # ── Step 6: Start websocket (blocking) ───────────────────────────────────
    ws_client = TickWebSocket(
        session=session,
        token=token,
        exchange=config.EXCHANGE,
        store=store,
        on_tick_callback=on_tick,
    )

    try:
        ws_client.connect()  # Blocks until disconnect
    except Exception as e:
        logger.error(f"Websocket fatal error: {e}")
        print(f"\n[FATAL] Websocket crashed: {e}")
    finally:
        # Ensure shutdown always runs even on unexpected crash
        if not shutdown_event.is_set():
            print("[INFO] Websocket exited unexpectedly. Saving data...")
            initiate_shutdown()


if __name__ == "__main__":
    main()
