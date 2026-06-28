# =============================================================================
# config.py — Fill in your Angel One credentials and stock settings here.
# Never commit this file to GitHub or share it publicly.
# =============================================================================

# ── Angel One SmartAPI Credentials ──────────────────────────────────────────
API_KEY: str = "your broker api"          # From SmartAPI dashboard
CLIENT_ID: str = "your client id"      # Your Angel One login ID (e.g. A123456)
PASSWORD: str = "your id password"        # Your Angel One login password
TOTP_SECRET: str = "write your toto id "  # Base32 secret from QR code setup

# ── Stock Settings ───────────────────────────────────────────────────────────
STOCK_SYMBOL: str = "TATASTEEL"   # NSE symbol exactly as listed (e.g. RELIANCE, TCS, INFY)
EXCHANGE: str = "NSE"            # "NSE" for equities, "NFO" for F&O

# ── Session Timing (IST) ─────────────────────────────────────────────────────
MARKET_OPEN_HOUR: int = 9
MARKET_OPEN_MINUTE: int = 15
MARKET_CLOSE_HOUR: int = 15
MARKET_CLOSE_MINUTE: int = 30

# ── Auto-Save Interval ───────────────────────────────────────────────────────
AUTOSAVE_INTERVAL_MINUTES: int = 15   # Save Excel backup every N minutes

# ── Output Directory ─────────────────────────────────────────────────────────
OUTPUT_DIR: str = "output"  # Folder where Excel + HTML files are saved

# ── Angel One Instrument Master URL ─────────────────────────────────────────
# Angel One publishes a fresh instrument list daily. This URL may change
# occasionally — check https://smartapi.angelbroking.com if downloads fail.
INSTRUMENT_MASTER_URL: str = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)

# ── Websocket Reconnect ───────────────────────────────────────────────────────
RECONNECT_DELAY_SECONDS: int = 10   # Wait before attempting reconnect on drop
MAX_RECONNECT_ATTEMPTS: int = 10    # Give up after this many consecutive failures
