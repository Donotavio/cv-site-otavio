---
name: chrome-devtools
description: Validate UIs in a live Chrome browser using the chrome-devtools MCP tools (screenshots, snapshots, audits, network inspection). Use for visual regression checks, accessibility audits, performance traces, and debugging front-end changes. NEVER kill the user's Chrome process or launch Chrome manually — let the MCP server manage the browser lifecycle.
---

# Skill: chrome-devtools — UI validation in a live browser

Use this skill every time you need to **visually verify** a frontend change
(HTML/CSS/JS render correctly, responsiveness, accessibility, performance,
runtime errors). The `chrome-devtools_*` MCP tools drive a real Chrome
instance and return screenshots, accessibility trees, console messages,
network requests, and Lighthouse audits.

## ⚠️ The single most important rule

**Never spawn Chrome yourself.** No `pkill`, no `open -a "Google Chrome"`,
no `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=...`.

The user has Chrome open with their own tabs (gmail, github, etc). Any
manual `pkill` or fresh `--remote-debugging-port` launch WILL close their
session and lose work. The MCP server is configured with `--autoConnect`
and manages the browser lifecycle by itself — when you call a tool like
`chrome-devtools_navigate_page`, it connects (or starts) the browser on
your behalf.

## When to use

- ✅ "Validate the hero renders correctly on mobile viewport"
- ✅ "Take a screenshot of the dashboard after the JS runs"
- ✅ "Audit accessibility on /world-cup-dashboard/"
- ✅ "Record a performance trace of the page load"
- ✅ "Check the browser console for runtime errors"
- ✅ "Verify dark mode toggle works"
- ❌ "Open the URL so I can see it" → use a tool below instead
- ❌ Running `curl` to validate JS-rendered content (the HTML will be the
  pre-hydration shell — useless for visual checks)

## Standard workflow

### 1. Discover what's already open

```
chrome-devtools_list_pages
```

Returns every tab the MCP server knows about. If there's already a page
matching your target, prefer `select_page` over opening a new one. The
user might already be looking at the dev site.

### 2. Open or reuse a page

- **Reuse**: `chrome-devtools_select_page` with the pageId from step 1.
- **New tab (background)**: `chrome-devtools_new_page` with `background: true`
  so we don't steal focus from the user.
- **Navigate existing**: `chrome-devtools_navigate_page` with the URL.

Prefer **background tabs** — we're validating, not browsing with the user.

### 3. Wait for content

```
chrome-devtools_wait_for(text=["Notícias ao vivo", "Estatísticas"], timeout=8000)
```

SPA / JS-rendered content is not present on first paint. Always wait for
a known string from the rendered DOM before snapshotting or screenshotting.

### 4. Inspect — pick the right tool

| Goal | Tool |
|---|---|
| Visual regression (pixels) | `chrome-devtools_take_screenshot` |
| Semantic structure (a11y tree, uids) | `chrome-devtools_take_snapshot` |
| Click / type / fill | `chrome-devtools_click`, `_fill`, `_fill_form` |
| Keyboard | `chrome-devtools_press_key` |
| Mobile / responsive | `chrome-devtools_resize_page` or `_emulate` |
| Dark / light mode | `chrome-devtools_emulate` with `colorScheme` |
| Runtime errors | `chrome-devtools_list_console_messages` |
| Network / API | `chrome-devtools_list_network_requests` |
| Run JS in page | `chrome-devtools_evaluate_script` |
| Accessibility + SEO + BP audit | `chrome-devtools_lighthouse_audit` |
| Performance trace | `chrome-devtools_performance_start_trace` |

**Snapshot vs Screenshot**: prefer `take_snapshot` for structure/interaction
(returns the a11y tree with `uid` you can click). Prefer `take_screenshot`
for visual sanity (compression, fullPage, element-only).

### 5. Test responsive breakpoints

Loop over common viewports with `chrome-devtools_resize_page`:

```python
for w, h in [(375, 667), (768, 1024), (1280, 800), (1920, 1080)]:
    resize(w, h)
    take_screenshot(filePath=f"/tmp/wc-{w}.png")
```

### 6. Audit accessibility + performance

```
chrome-devtools_lighthouse_audit(mode="navigation", device="mobile")
```

Returns scores for accessibility, SEO, best practices. For performance,
use `performance_start_trace` (reloads + records) then read insights.

### 7. Cleanup

```
chrome-devtools_close_page(pageId=...)
```

Only close pages you opened. **Never close the last open page** — the
tool itself enforces this, but be explicit.

## Patterns by task

### Visual regression of a single component

1. `navigate_page` to the page
2. `wait_for` a string inside the component
3. `take_snapshot` → find the component's `uid`
4. `take_screenshot(uid=...)` — element-only screenshot
5. Compare against expected (visual diff if you have a baseline)

### Console errors after a code change

```
chrome-devtools_navigate_page(url=..., ignoreCache=true)
chrome-devtools_list_console_messages(types=["error", "warn"])
```

If errors → `chrome-devtools_get_console_message(msgid=...)` for full detail
(including source-mapped stack traces).

### Performance regression check

```
chrome-devtools_navigate_page(url=...)        # make sure we're on the right URL
chrome-devtools_performance_start_trace(reload=true, autoStop=true)
# → automatic stop, returns insights + key metrics (LCP, INP, CLS)
chrome-devtools_performance_analyze_insight(insightSetId=..., insightName="LCPBreakdown")
```

### "Does X work on mobile?"

```
chrome-devtools_emulate(viewport="375x667x2,mobile,touch")
chrome-devtools_take_screenshot()
# Reset:
chrome-devtools_emulate(viewport="")
```

## Anti-patterns — DON'T

- ❌ `pkill -9 -f "Google Chrome"` — closes the user's tabs
- ❌ `"/Applications/Google Chrome.app/..." --remote-debugging-port=9222 &`
  — starts a second instance that conflicts with the MCP-managed one
- ❌ `curl localhost:4321/...` to validate JS-rendered SPA content
- ❌ Closing a page the user opened (always check `list_pages` first)
- ❌ Calling `take_screenshot` without first waiting for content (blank page)
- ❌ Iterating blind — always snapshot before clicking, so you know the uid

## KB / reference docs

- [`kb/troubleshooting.md`](kb/troubleshooting.md) — common errors and fixes
- [`kb/configuration.md`](kb/configuration.md) — how `~/.config/opencode/opencode.json` wires the MCP
- [`kb/tool-cheatsheet.md`](kb/tool-cheatsheet.md) — every tool with args + when to use

## First-run setup (one time, by the user)

The MCP is configured with **`--isolated`** in
`~/.config/opencode/opencode.json`:

```json
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
```

**What `--isolated` does**: the MCP launches its OWN Chrome instance in
a throwaway profile (`~/.cache/chrome-devtools-mcp/chrome-profile-stable/`),
wiped on close. It NEVER touches the user's Chrome — no shared cookies,
no shared session, no risk of killing their tabs.

This is the safest config. Trade-off: the isolated profile has no login
state, so any page behind auth (GitHub private repo, dashboard with
cookies) needs re-login each session.

**Alternatives** (don't combine):
- `--autoConnect` — connect to user's Chrome 144+ with remote debugging
  enabled via `chrome://inspect/#remote-debugging`. Risky: races with
  manual launches.
- `--browser-url=http://127.0.0.9:9222` — connect to a specific Chrome
  the user started themselves with `--remote-debugging-port=9222`.
