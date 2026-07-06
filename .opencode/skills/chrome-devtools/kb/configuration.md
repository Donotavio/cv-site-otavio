# chrome-devtools MCP — configuration

## Where it lives

`~/.config/opencode/opencode.json` — global opencode config shared by
every project on this machine. Current setup (safest — `--isolated`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "chrome-devtools": {
      "type": "local",
      "command": [
        "npx", "-y", "chrome-devtools-mcp",
        "--isolated",
        "--screenshot-format=jpeg",
        "--screenshot-quality=72",
        "--screenshot-max-width=1600"
      ],
      "enabled": true
    }
  }
}
```

## What `--isolated` does (current config)

Launches the MCP's OWN Chrome instance in a throwaway profile at
`~/.cache/chrome-devtools-mcp/chrome-profile-stable/`, wiped on close.
**Never touches the user's Chrome** — no shared cookies, no shared
session, no risk of killing their tabs.

Trade-off: the isolated profile has no login state. Pages behind auth
need re-login each session (or skip auth-protected pages in validation).

This is the **recommended default** for opencode agents that don't have
permission gates for `kill`/`pkill`. Prevents the "you closed my Chrome"
class of accident.

## Useful extra flags (add to `args` array)

| Flag | Effect |
|---|---|
| `--headless` | Run headless (no UI). Faster CI-like runs but the user can't see what's happening. |
| `--isolated` | Use a throwaway temp profile that's wiped on close. |
| `--channel=canary` | Use Chrome Canary instead of Stable. |
| `--executable-path=/path/to/chrome` | Use a specific Chrome binary (Chrome for Testing, etc). |
| `--viewport=1280x720` | Initial viewport size. |
| `--proxy-server=...` | Route traffic through a proxy. |
| `--accept-insecure-certs` | For local HTTPS dev with self-signed certs. |
| `--screenshot-format=jpeg` | Smaller screenshots (~3-5x smaller than PNG). |
| `--screenshot-quality=70` | JPEG quality (0-100). |
| `--screenshot-max-width=1280` | Downscale screenshots to save context. |
| `--no-usage-statistics` | Opt out of Google's telemetry. |
| `--slim` | Expose only 3 tools (navigate, evaluate, screenshot). For minimal setups. |
| `--experimentalPageIdRouting` | Required if multiple agents share one server. |

## Recommended config for this project

This project has multiple dashboards (Brasil Cockpit, PIX Observatory,
World Cup, Data Stack Radar) that we validate visually. A good balance
of speed and quality:

```json
{
  "mcp": {
    "chrome-devtools": {
      "type": "local",
      "command": [
        "npx", "-y", "chrome-devtools-mcp",
        "--autoConnect",
        "--screenshot-format=jpeg",
        "--screenshot-quality=72",
        "--screenshot-max-width=1600"
      ],
      "enabled": true
    }
  }
}
```

JPEG 72 saves ~3-5x context vs PNG and is plenty for visual regression.

## Connecting to a specific Chrome (alternative)

If the user wants to debug a Chrome they started themselves with a known
port:

```json
{
  "mcp": {
    "chrome-devtools": {
      "command": [
        "npx", "-y", "chrome-devtools-mcp",
        "--browser-url=http://127.0.0.1:9222"
      ]
    }
  }
}
```

This replaces `--autoConnect`. **The user** starts Chrome with
`--remote-debugging-port=9222` (their responsibility, not ours).

## Per-project overrides

Opencode merges `~/.config/opencode/opencode.json` with project-level
`opencode.json` (if present at repo root). To disable chrome-devtools
for a specific project:

```json
// <repo>/opencode.json
{
  "mcp": {
    "chrome-devtools": { "enabled": false }
  }
}
```

## Updating

`npx -y chrome-devtools-mcp` always pulls `latest` from npm. To pin a
version (reproducible CI), replace with `chrome-devtools-mcp@0.x.y`.

Check installed version:

```bash
npx chrome-devtools-mcp --version
```

Update check runs periodically; to disable:
`CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1` env var.
