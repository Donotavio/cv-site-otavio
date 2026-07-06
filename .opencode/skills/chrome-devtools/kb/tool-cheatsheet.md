# chrome-devtools MCP — tool cheatsheet

All tools are prefixed `chrome-devtools_`. Args shown as `name: type`.
Optional args omitted unless commonly needed.

## Navigation (6 tools)

### `list_pages`
Lists every page/tab the MCP knows about. **Always call first** to see
what's already open before opening new tabs.

Returns: array of `{ pageId, url, title }`.

### `new_page(url: string, background: bool = false, isolatedContext?: string)`
Opens a new tab. Use `background: true` to not steal focus from the user.

```js
new_page(url="http://localhost:4321/world-cup-dashboard/", background=true)
```

### `select_page(pageId: number, bringToFront: bool = false)`
Switches the active page. Use after `list_pages` to operate on a
specific tab. `bringToFront=true` focuses the tab in the user's window.

### `navigate_page(url?: string, type?: "url"|"back"|"forward"|"reload", ignoreCache?: bool)`
Navigate the active page. For "validate after deploy" flows, always
`ignoreCache: true`.

### `close_page(pageId: number)`
Closes a tab. **Never close the last open page** — tool refuses anyway.

### `wait_for(text: string[], timeout?: int)`
Blocks until any of the strings appears on the page. **Use before every
screenshot/snapshot of a JS-rendered SPA.**

```js
wait_for(text=["Jogos disputados", "Estatísticas"], timeout=8000)
```

## Input (10 tools)

### `take_snapshot(verbose?: bool, filePath?: string)`
Returns the a11y tree with `uid`s for every element. **Preferred over
screenshot** for structure / interaction — you get text, roles, states.

Use `verbose=true` for full a11y info. Use `filePath` to dump the full
tree to disk when it's huge.

### `take_screenshot(format?: "png"|"jpeg"|"webp", quality?: int, fullPage?: bool, uid?: string, filePath?: string)`
Captures pixels. `uid` for element-only; `fullPage` for whole page.

```js
take_screenshot(format="jpeg", quality=72, fullPage=true, filePath="/tmp/wc-full.jpeg")
```

### `click(uid: string, dblClick?: bool, includeSnapshot?: bool)`
Click an element by its snapshot `uid`. Re-snapshot first if anything
might have changed.

### `fill(uid: string, value: string, includeSnapshot?: bool)`
Type into an input/textarea. For `<select>`, pass the option value.

### `fill_form(elements: [{uid, value}], includeSnapshot?: bool)`
**Batch** — fill multiple fields at once. Always prefer this over
sequential `fill` calls.

### `hover(uid: string)`
Triggers `:hover` state (dropdowns, tooltips).

### `press_key(key: string)`
Keyboard events. Examples: `"Enter"`, `"Tab"`, `"Escape"`,
`"Control+Shift+R"`, `"Meta+A"`.

### `type_text(text: string, submitKey?: string)`
Type into the currently-focused input (after a `click` on it). Use
`submitKey="Enter"` to submit a form.

### `drag(from_uid: string, to_uid: string)`
Drag-and-drop between two elements.

### `upload_file(uid: string, filePath: string)`
Upload via `<input type="file">`.

## Emulation (2 tools)

### `emulate(viewport?: string, colorScheme?: "light"|"dark"|"auto", userAgent?: string, networkConditions?: string, geolocation?: string, cpuThrottlingRate?: number, extraHttpHeaders?: string)`
Apply emulation. Pass empty string to clear each field.

```js
// iPhone-like
emulate(viewport="375x667x3,mobile,touch", colorScheme="dark")
// Reset
emulate(viewport="", colorScheme="auto")
```

Network conditions: `"Offline"|"Slow 3G"|"Fast 3G"|"Slow 4G"|"Fast 4G"`.

### `resize_page(width: int, height: int)`
Resize the viewport. Faster than `emulate` for one-off responsive tests.

## Performance (3 tools)

### `performance_start_trace(reload?: bool = true, autoStop?: bool = true, filePath?: string)`
Begins a trace. **Navigate to the URL first**, then start. Reload
happens after recording starts so first paint is captured.

```js
navigate_page(url="https://example.com/")
performance_start_trace(reload=true, autoStop=true)
// → returns insights + LCP/INP/CLS
```

### `performance_stop_trace(filePath?: string)`
Manual stop if `autoStop: false`. Returns the same payload.

### `performance_analyze_insight(insightSetId: string, insightName: string)`
Drill into a specific insight from the trace response. Names like
`"LCPBreakdown"`, `"DocumentLatency"`, `"RenderBlocking"`.

## Network (2 tools)

### `list_network_requests(resourceTypes?: string[], includePreservedRequests?: bool, pageSize?: int, pageIdx?: int)`
All requests since last navigation. Filter by type: `"xhr"`, `"fetch"`,
`"document"`, `"script"`, `"stylesheet"`, etc.

### `get_network_request(reqid?: int, requestFilePath?: string, responseFilePath?: string)`
Inspect one request — headers, body, response. Use `FilePath` args for
large bodies (don't inline them in the response).

## Debugging (8 tools)

### `list_console_messages(types?: string[], includePreservedMessages?: bool, pageSize?: int)`
Messages since last nav. `types`: `"error"|"warn"|"log"|"info"|"debug"`.

### `get_console_message(msgid: int)`
Full message detail with source-mapped stack trace.

### `evaluate_script(function: string, args?: string[], filePath?: string, dialogAction?: string)`
Run JS in the page. Function declaration, not expression:

```js
evaluate_script(function="() => { return { title: document.title, url: location.href } }")
```

With args (uids resolved to elements):

```js
evaluate_script(function="(el) => el.textContent", args=["uid-from-snapshot"])
```

### `lighthouse_audit(mode?: "navigation"|"snapshot", device?: "desktop"|"mobile", outputDirPath?: string)`
Full audit (accessibility, SEO, best practices, agentic). For perf, use
`performance_start_trace`.

### `take_heapsnapshot(filePath: string)`
Memory leak analysis. Always pass `filePath` — these are large.

## Workflow: "validate after deploy"

```js
// 1. Discover
list_pages

// 2. Navigate (reuse if page exists, else open)
new_page(url="https://donotavio.github.io/cv-site-otavio/world-cup-dashboard/", background=true)
// or
select_page(pageId=42, bringToFront=false)
navigate_page(url="...", ignoreCache=true)

// 3. Wait for SPA to render
wait_for(text=["Notícias ao vivo", "Estatísticas"], timeout=10000)

// 4. Check console
list_console_messages(types=["error", "warn"])

// 5. Visual checks
take_screenshot(format="jpeg", quality=72, filePath="/tmp/wc-1.jpeg")

// 6. Responsive sweep
resize_page(width=375, height=667)
take_screenshot(filePath="/tmp/wc-mobile.jpeg")
resize_page(width=1920, height=1080)

// 7. A11y audit
lighthouse_audit(mode="snapshot", device="desktop")

// 8. Cleanup (only if we opened it)
close_page(pageId=...)
```
