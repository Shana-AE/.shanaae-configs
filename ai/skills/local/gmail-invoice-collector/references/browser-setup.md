# Browser Setup for Gmail Automation

Gmail requires an **interactive login** (often 2FA) that only the user can
perform, and attachment downloads need a **real user gesture** that synthetic
clicks cannot provide. Therefore: launch a *real, visible* browser the user can
see and log into, expose Chrome DevTools Protocol (CDP), then drive it over CDP.

## General approach (any system)

Launch Chromium/Chrome/Brave/Edge with remote debugging on a fixed port, a
dedicated user-data-dir, and (if the network needs it) a proxy:

```bash
<browser-binary> \
  --remote-debugging-port=9222 \
  --remote-debugging-address=127.0.0.1 \
  --user-data-dir=/tmp/gmail-automation \
  --no-first-run --no-default-browser-check \
  --password-store=basic --use-mock-keychain \
  [--proxy-server=http://127.0.0.1:7897] \
  "https://mail.google.com"
```

Then verify the CDP endpoint and connect any tool to it:

```bash
curl -s http://127.0.0.1:9222/json/version        # health check
curl -s http://127.0.0.1:9222/json | jq '.[] | select(.type=="page")'   # targets
```

Drive it with: `agent-browser --cdp 9222 ...`, Playwright/Puppeteer
`connectOverCDP('http://127.0.0.1:9222')`, chrome-devtools-mcp
(`--browserUrl http://127.0.0.1:9222`), or raw CDP over WebSocket.

## ⚠️ agent-browser caveat

`agent-browser --headed` frequently still launches **headless**
(`--headless=new --ozone-platform=headless`) because of a persistent daemon —
the user sees **no window** and cannot log in. If a window does not appear,
**abandon agent-browser's own browser** and launch a real one manually as above,
then connect via `--cdp 9222`.

## System-specific notes

### WSL2 (Windows) — WSLg
GUI apps display on the Windows desktop via WSLg. Confirm WSLg is active
(`echo $DISPLAY` → `:0`; `/mnt/wslg` exists). Launch with the Linux Chrome
binary; the window appears on Windows. Proxies are common here (reach Google).

### Linux desktop
Set `DISPLAY` (X11) or run natively (Wayland). Straightforward — a window shows.

### macOS / Windows native
Launch Chrome/Edge/Brave with `--remote-debugging-port=9222`. On macOS the
binary is e.g. `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
The normal window appears.

### Headless server (no display)
There is no screen for the user to log into. Options:
1. **Best:** the user logs into Gmail in *their own* browser on a machine with a
   display; expose that browser's CDP and connect remotely.
2. Run a headed browser inside a virtual framebuffer (`Xvfb`) + stream it via
   noVNC/browser streaming so the user can interact remotely.
3. Reuse a long-lived browser profile that is *already* logged in (load its
   user-data-dir / saved state) and skip interactive login.

## Security (important)
- **Never type or store the user's password or 2FA.** The user performs login
  themselves in the visible window.
- Watch for Gmail's **"Show password"** checkbox being ticked — it exposes the
  password in plaintext on the page. Tell the user to uncheck it and to consider
  rotating the password afterward.
- When done, close the automation browser so the logged-in session does not
  persist: `pkill -f remote-debugging-port=9222`.
