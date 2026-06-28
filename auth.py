# =============================================================================
# auth.py — Handles Angel One SmartAPI authentication.
#
# Angel One uses TOTP-based 2FA. The TOTP code changes every 30 seconds,
# so we MUST call pyotp.now() at login time — never cache the code or pass
# it as a static string. This is the #1 cause of "Invalid TOTP" errors.
# =============================================================================

import logging
from dataclasses import dataclass

import pyotp
from SmartApi import SmartConnect

import config

logger = logging.getLogger(__name__)


@dataclass
class AuthSession:
    """Holds all session data needed for websocket and API calls."""
    smart_api: SmartConnect
    auth_token: str
    feed_token: str
    client_id: str


def login() -> AuthSession:
    """
    Authenticate with Angel One SmartAPI using credentials from config.py.

    TOTP note: pyotp.now() is called inside this function at the moment of
    login. Do not pre-compute or cache the TOTP — it expires every 30 seconds
    and a stale value will cause authentication to fail silently or with a
    cryptic error from Angel One's server.

    Returns:
        AuthSession dataclass with smart_api instance, tokens, and client ID.

    Raises:
        Exception: With a descriptive message if login fails.
    """
    logger.info(f"Logging in as {config.CLIENT_ID}...")

    smart_api = SmartConnect(api_key=config.API_KEY)

    # Generate TOTP at this exact moment — must be fresh
    totp_code = pyotp.TOTP(config.TOTP_SECRET).now()
    logger.debug("TOTP generated successfully.")

    try:
        session_data = smart_api.generateSession(
            clientCode=config.CLIENT_ID,
            password=config.PASSWORD,
            totp=totp_code,
        )
    except Exception as e:
        _diagnose_login_error(e)
        raise

    # Angel One returns a dict with status + data on success
    if not session_data or session_data.get("status") is False:
        message = session_data.get("message", "Unknown error") if session_data else "No response"
        _print_login_failure_help(message)
        raise Exception(f"Login failed: {message}")

    auth_token: str = session_data["data"]["jwtToken"]
    feed_token: str = smart_api.getfeedToken()

    logger.info("Login successful.")

    return AuthSession(
        smart_api=smart_api,
        auth_token=auth_token,
        feed_token=feed_token,
        client_id=config.CLIENT_ID,
    )


def _diagnose_login_error(error: Exception) -> None:
    """
    Print a human-readable diagnosis for common login failures.

    Args:
        error: The exception caught during generateSession().
    """
    msg = str(error).lower()
    if "totp" in msg or "otp" in msg:
        print("\n[AUTH ERROR] TOTP validation failed.")
        print("  → Check that TOTP_SECRET in config.py matches the Base32 secret")
        print("    shown when you set up 2FA (not the 6-digit code — the secret key).")
        print("  → Make sure your system clock is accurate (TOTP is time-sensitive).")
    elif "invalid" in msg and "api" in msg:
        print("\n[AUTH ERROR] Invalid API key.")
        print("  → Check API_KEY in config.py matches your SmartAPI dashboard key.")
        print("  → Ensure the API key is active (not expired or revoked).")
    elif "password" in msg:
        print("\n[AUTH ERROR] Incorrect password.")
        print("  → Use your Angel One trading password, not your PIN.")
    else:
        print(f"\n[AUTH ERROR] Unexpected error: {error}")
        print("  → Check your internet connection.")
        print("  → Verify all credentials in config.py are correct.")


def _print_login_failure_help(message: str) -> None:
    """
    Print help text when Angel One returns status=False on login.

    Args:
        message: Error message from Angel One's API response.
    """
    print(f"\n[LOGIN FAILED] Angel One returned: {message}")
    print("Common causes:")
    print("  1. Wrong CLIENT_ID — use your Angel One login ID (e.g. A123456)")
    print("  2. Account locked — too many failed attempts, reset via Angel One app")
    print("  3. SmartAPI not activated — activate at smartapi.angelbroking.com")
    print("  4. API key not linked to your account properly")
