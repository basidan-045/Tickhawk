# TickHawk — Setup Guide (Angel One SmartAPI)

Complete step-by-step instructions to go from zero to live tick capture.

---

## Step 1: Activate SmartAPI on Your Angel One Account

1. Go to **https://smartapi.angelbroking.com**
2. Log in with your Angel One credentials
3. Click **"Create an App"**
4. Fill in:
   - App Name: anything (e.g. "TickHawk")
   - App Type: **Trading**
   - Redirect URL: `https://localhost` (required field, not actually used)
5. Submit and copy your **API Key** — paste it into `config.py → API_KEY`

---

## Step 2: Set Up TOTP (2FA)

Angel One requires TOTP-based two-factor authentication for API logins.

1. Open the **Angel One mobile app**
2. Go to: **My Account → Profile → Security Settings → Enable TOTP**
3. You'll see a QR code and below it a **Base32 secret key** (looks like: `JBSWY3DPEHPK3PXP`)
4. Copy that Base32 secret → paste into `config.py → TOTP_SECRET`

> **IMPORTANT:** Do NOT enter the 6-digit code shown on your screen.
> Enter the long Base32 secret key that the QR code encodes.
> The 6-digit code changes every 30 seconds — the Base32 secret is permanent.

If you already set up TOTP and didn't save the secret:
- Disable TOTP in the app and re-enable it — the secret will be shown again.

---

## Step 3: Fill In config.py

Open `config.py` and replace every `YOUR_..._HERE` placeholder:

```python
API_KEY      = "abc123xyz..."      # From SmartAPI dashboard
CLIENT_ID    = "A123456"           # Your Angel One login ID
PASSWORD     = "your_password"     # Your Angel One trading password
TOTP_SECRET  = "JBSWY3DPEHPK3PXP" # Base32 secret from Step 2

STOCK_SYMBOL = "RELIANCE"          # NSE symbol exactly as listed
EXCHANGE     = "NSE"               # NSE for stocks, NFO for F&O
```

**Finding the exact NSE symbol:**
- Go to https://www.nseindia.com → search your stock
- The symbol shown in the URL/header is what to use
- Examples: `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `NIFTY50` (for index F&O)

---

## Step 4: Install Python Dependencies

Make sure you have Python 3.10 or higher:
```bash
python --version
```

Install all dependencies:
```bash
pip install -r requirements.txt
```

---

## Step 5: Test Login First (Don't Skip This)

Before running the full system, test login in isolation:

```bash
python -c "
from auth import login
session = login()
print('Login OK. Feed token:', session.feed_token[:20], '...')
"
```

Expected output:
```
Logging in as A123456...
Login successful.
Login OK. Feed token: eyJhbGciOiJ...
```

If this fails, fix it before proceeding. Common errors:

| Error | Fix |
|-------|-----|
| `Invalid TOTP` | Check TOTP_SECRET is Base32 key, not the 6-digit code |
| `Invalid API Key` | Re-copy key from SmartAPI dashboard |
| `Wrong password` | Use trading password, not Angel One PIN |
| `Account locked` | Reset via Angel One app → Forgot Password |

---

## Step 6: Test Token Lookup

```bash
python -c "
from instrument import resolve_symbol_to_token
import config
token = resolve_symbol_to_token(config.STOCK_SYMBOL, config.EXCHANGE)
print(f'Token for {config.STOCK_SYMBOL}: {token}')
"
```

If symbol not found, it will suggest close matches. Fix `STOCK_SYMBOL` in config.py.

---

## Step 7: Run the Full System

```bash
python main.py
```

**If run before 9:15 AM:**
The system will wait and print a countdown until market open.

**During market hours:**
You'll see live tick output:
```
09:15:01.342 | RELIANCE |  ₹2,847.50 | Ticks today: 1
09:15:01.891 | RELIANCE |  ₹2,847.55 | Ticks today: 2
09:15:02.103 | RELIANCE |  ₹2,847.50 | Ticks today: 3
```

**At 3:30 PM:**
System auto-shuts down, saves Excel and opens the chart in your browser.

**To stop early:**
Press `Ctrl+C` — data is always saved before exit.

---

## Output Files

All files saved in the `output/` folder:

| File | Description |
|------|-------------|
| `RELIANCE_27-06-2026.xlsx` | All ticks — Time column + Price column |
| `RELIANCE_27-06-2026.html` | Interactive Plotly chart — open in any browser |
| `errors_27-06-2026.log` | Error log for the session |

---

## Common Issues

**"No ticks arriving" — websocket connects but no data:**
- Verify the stock is actively trading (not halted or suspended)
- Check that your API key has websocket permissions enabled in SmartAPI dashboard
- Some API keys require enabling "Market Data" scope separately

**"Instrument token not found":**
- NSE symbols are case-sensitive — use UPPERCASE
- Some symbols differ from company name: HDFC Bank → `HDFCBANK`, not `HDFC BANK`
- Try the NSE website to confirm the exact ticker

**Excel file has too many rows to open in standard Excel:**
- Excel handles up to 1,048,576 rows — for a heavily traded stock you won't hit this
- If needed, split by hour using pandas: `df[df['Time'].str.startswith('09')]`

**System clock issue (TOTP always fails):**
```bash
# Sync system time (Linux/Mac)
sudo ntpdate -u time.google.com

# Windows: Control Panel → Date and Time → Internet Time → Sync Now
```

---

## File Structure

```
tickhawk/
├── config.py           ← YOUR CREDENTIALS GO HERE
├── main.py             ← Run this
├── auth.py             ← Login logic
├── websocket_client.py ← Live tick capture
├── data_store.py       ← In-memory storage
├── instrument.py       ← Token lookup
├── exporter.py         ← Excel writer
├── grapher.py          ← Plotly chart
├── requirements.txt    ← Dependencies
├── SETUP.md            ← This file
└── output/             ← Created automatically
    ├── RELIANCE_DD-MM-YYYY.xlsx
    └── RELIANCE_DD-MM-YYYY.html
```
