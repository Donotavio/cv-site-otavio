# chrome-devtools MCP — troubleshooting

## Error: "Could not connect to Chrome. Check if Chrome is running."
### Cause: "Could not find DevToolsActivePort for chrome at .../DevToolsActivePort"

The MCP server can't find a debuggable Chrome. **With our `--isolated`
config**, just retry the tool — the MCP spawns its own Chrome in a
throwaway profile (`~/.cache/chrome-devtools-mcp/chrome-profile-stable/`)
on demand. No user action needed.

### Why this is safe

`--isolated` means the MCP's Chrome has its own profile, separate from
the user's. **Never** combine `--isolated` with manual Chrome launches
on the same machine — they don't conflict, but launching Chrome yourself
creates a second browser that the MCP doesn't know about.

### Do NOT try to "help" by starting Chrome

That creates a second browser and races with the MCP's auto-launch. Just
retry the tool — if it still fails after 2-3 retries, ask the user to
check the MCP server logs.

### If you really need to use the user's Chrome

Switch the config from `--isolated` to `--autoConnect` (requires Chrome
144+ with remote debugging enabled via `chrome://inspect/#remote-debugging`)
or `--browser-url=http://127.0.0.1:9222` (user starts Chrome with
`--remote-debugging-port=9222` themselves).

## Error: "The last open page cannot be closed."

`close_page` refuses to close the last page in the browser. By design —
Chrome can't run without at least one tab. Either:

- Open a new page first, then close the old one, or
- Just navigate the existing page to your next target instead of closing.

## Error: clicking an uid from a stale snapshot

If you snapshot, then the page re-renders (e.g., a chart hydrated), the
`uid`s are invalid. Symptom: `click` returns "element not found".

**Fix:** always re-snapshot before clicking if anything might have changed.
Snapshots are cheap; debugging a stale-uid click is not.

## Blank / white screenshot

Causes (most → least common):

1. **Did not wait for content.** SPA shell renders before JS hydrates.
   Use `wait_for(text=[...])` with a known string from the rendered DOM.
2. **Tab is in the background and lazy-renders.** Some charts pause when
   not visible. Use `select_page(bringToFront=true)` or wait longer.
3. **CSP blocked a CDN script.** Check `list_console_messages` for CSP
   violations and adjust the policy.
4. **Viewport too small for the layout.** `resize_page` to desktop first.

## Lighthouse audit returns "navigation timeout"

The audit navigates and waits for network idle. If the page keeps making
requests (long polling, analytics loops), it never settles. Use:

```
chrome-devtools_lighthouse_audit(mode="snapshot")
```

`snapshot` analyzes the current state without reloading — useful for
pages with continuous network activity.

## Performance trace returns no insights

`performance_start_trace(reload=true)` reloads the page. If the URL is
`about:blank` or `chrome://intro/`, the reload fails silently. Always
`navigate_page` to the real URL BEFORE starting the trace.

## Screenshot is huge and eats context

Use `format="jpeg"` with `quality=70` for visual diffs, or
`format="webp"` for even smaller. PNG only for pixel-perfect checks.

The MCP server can also be configured once with global defaults via
`--screenshot-format=jpeg --screenshot-quality=70 --screenshot-max-width=1280`
in `~/.config/opencode/opencode.json`.

## Tool returns HTTP 500 / Internal error

Usually transient. Wait 2s and retry. If it persists, the Chrome instance
is wedged — ask the user to restart their Chrome (just close and reopen
the app, no flags), then retry.

## "Cannot find context" / "Target closed"

The page crashed or was closed underneath us. Re-list pages, re-select
or open a new one. Often happens after `evaluate_script` with an infinite
loop or out-of-memory operation.
