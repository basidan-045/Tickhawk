# =============================================================================
# websocket_client.py — Angel One SmartWebSocket V2 tick data capture.
#
# WHY SmartWebSocket V2? Angel One deprecated V1 in 2023. V1 connections
# are silently dropped or return empty data — always use V2.
#
# The websocket runs on its own internal thread (managed by the SmartApi SDK).
# Our on_data callback fires each time a new tick arrives and appends to
# the shared TickStore via add_tick() which is lock-protected.
# =============================================================================

import logging
import time
from typing import Callable

from SmartApi.smartWebSocketV2 import SmartWebSocketV2

import config
from auth import AuthSession
from data_store import TickStore

logger = logging.getLogger(__name__)

# Angel One subscription mode constants
MODE_LTP = 1          # Last Traded Price only — lowest bandwidth, what we need
MODE_QUOTE = 2        # LTP + top bid/ask
MODE_SNAP_QUOTE = 3   # Full market depth — unnecessary for this project


class TickWebSocket:
    """
    Manages the Angel One SmartWebSocket V2 connection lifecycle.

    Subscribes to LTP updates for a single instrument and feeds every
    price update into the provided TickStore. Handles reconnection
    automatically if the connection drops mid-session.
    """

    def __init__(
        self,
        session: AuthSession,
        token: str,
        exchange: str,
        store: TickStore,
        on_tick_callback: Callable[[float, int], None],
    ) -> None:
        """
        Initialize the websocket client.

        Args:
            session:            AuthSession from auth.login().
            token:              Instrument token from instrument.py.
            exchange:           Exchange string (e.g. "NSE").
            store:              TickStore to write ticks into.
            on_tick_callback:   Called after each tick with (price, total_count).
                                Use this for console printing in main.py.
        """
        self._session = session
        self._token = token
        self._exchange = exchange
        self._store = store
        self._on_tick_callback = on_tick_callback
        self._sws: SmartWebSocketV2 | None = None
        self._running: bool = False
        self._reconnect_count: int = 0

        # Subscription token list format required by Angel One V2
        self._token_list = [
            {
                "exchangeType": self._exchange_type_code(exchange),
                "tokens": [token],
            }
        ]

    @staticmethod
    def _exchange_type_code(exchange: str) -> int:
        """
        Convert exchange string to Angel One's numeric exchange type.

        Angel One V2 uses integers not strings for exchange identification.
        This is undocumented in older SDK versions — a common source of
        'subscription failed' errors.

        Args:
            exchange: Exchange name string.

        Returns:
            Integer exchange type code.

        Raises:
            ValueError: If exchange string is not recognized.
        """
        mapping = {
            "NSE": 1,
            "NFO": 2,
            "BSE": 3,
            "BFO": 4,
            "MCX": 5,
            "NCDEX": 7,
            "CDS": 13,
        }
        code = mapping.get(exchange.upper())
        if code is None:
            raise ValueError(
                f"Unknown exchange '{exchange}'. Valid options: {list(mapping.keys())}"
            )
        return code

    def _on_open(self, wsapp) -> None:
        """Called when websocket connection is established."""
        logger.info("Websocket connected. Subscribing to tick feed...")
        self._reconnect_count = 0  # Reset on successful connection
        self._sws.subscribe(
            correlation_id="tick_feed",
            mode=MODE_LTP,
            token_list=self._token_list,
        )
        logger.info(f"Subscribed to token {self._token} on {self._exchange} (LTP mode).")

    def _on_data(self, wsapp, message: dict) -> None:
        """
        Called for every incoming tick message from Angel One.

        Angel One V2 sends LTP in the 'last_traded_price' field as an
        integer in paise (1/100th of a rupee). Divide by 100 to get INR.

        Args:
            wsapp:   Websocket app instance (unused directly).
            message: Dict containing tick data.
        """
        try:
            # Price arrives in paise — divide by 100 for rupees
            price_paise: int = message.get("last_traded_price", 0)
            if price_paise == 0:
                return  # Skip zero-price phantom ticks (can occur at session start)

            price_inr: float = price_paise / 100.0
            total_count = self._store.add_tick(price_inr)
            self._on_tick_callback(price_inr, total_count)

        except Exception as e:
            logger.error(f"Error processing tick: {e} | Raw message: {message}")

    def _on_error(self, wsapp, error) -> None:
        """Called when a websocket error occurs."""
        logger.error(f"Websocket error: {error}")

    def _on_close(self, wsapp) -> None:
        """
        Called when the websocket connection closes.

        If we're supposed to be running (not a clean shutdown), attempt
        to reconnect after a delay.
        """
        logger.warning("Websocket connection closed.")
        if self._running:
            self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        """
        Attempt to reconnect after an unexpected disconnect.

        Waits RECONNECT_DELAY_SECONDS between attempts. Stops after
        MAX_RECONNECT_ATTEMPTS consecutive failures.
        """
        self._reconnect_count += 1
        if self._reconnect_count > config.MAX_RECONNECT_ATTEMPTS:
            logger.error(
                f"Exceeded {config.MAX_RECONNECT_ATTEMPTS} reconnect attempts. "
                "Stopping. Data captured so far is preserved in memory."
            )
            self._running = False
            return

        logger.warning(
            f"Reconnect attempt {self._reconnect_count}/{config.MAX_RECONNECT_ATTEMPTS} "
            f"in {config.RECONNECT_DELAY_SECONDS}s..."
        )
        print(
            f"\n[RECONNECT] Attempt {self._reconnect_count} in "
            f"{config.RECONNECT_DELAY_SECONDS}s — data preserved."
        )
        time.sleep(config.RECONNECT_DELAY_SECONDS)
        self.connect()

    def connect(self) -> None:
        """
        Create a new SmartWebSocketV2 instance and start the connection.

        Called on initial start and on each reconnect attempt.
        """
        self._sws = SmartWebSocketV2(
            auth_token=self._session.auth_token,
            api_key=config.API_KEY,
            client_code=self._session.client_id,
            feed_token=self._session.feed_token,
        )
        self._sws.on_open = self._on_open
        self._sws.on_data = self._on_data
        self._sws.on_error = self._on_error
        self._sws.on_close = self._on_close

        self._running = True
        logger.info("Starting SmartWebSocket V2 connection...")
        self._sws.connect()  # Blocking — runs until disconnected

    def disconnect(self) -> None:
        """
        Cleanly close the websocket connection.

        Sets _running = False first so the on_close callback does NOT
        trigger a reconnect attempt.
        """
        logger.info("Closing websocket connection...")
        self._running = False
        if self._sws:
            try:
                self._sws.close_connection()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
