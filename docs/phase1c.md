# Phase 1c — Web UI Architecture, Security & Correctness Review

## 1. UI Architecture

### Tab structure

The UI is a single-page application served from `static/index.html`. All navigation is
client-side: a fixed topbar holds four `<button class="tab-btn">` elements; `activateTab()`
toggles the `.active` class on the corresponding `.tab-pane` div without any page reload.
The graph tab is pre-activated on first load; all other tabs lazy-load their data on first
activation via `onTabFirstActivate()`.

| Tab   | Pane element  | First-activation action |
| ----- | ------------- | ----------------------- |
| Graph | `#graph-pane` | `loadGraph()`           |
| Logs  | `#logs-pane`  | `loadLogs()`            |
| RAG   | `#rag-pane`   | `loadEmbeddingStats()`  |
| Crons | `#crons-pane` | none (static content)   |

### Data flow — API calls per tab

**Graph tab**

- `GET /conversation/recent?limit=50` → conversation nodes
- `GET /memory/list` → memory nodes
- Both fetched in parallel via `Promise.all`.

**Logs tab**

- `GET /conversation/recent?limit=<N>` (N starts at 100, increments by 100 on "Load more")
- Client-side filter applied in `renderLogs()` against the cached `lastLogEntries` array.

**RAG tab**

- `GET /search/semantic?q=<query>` or `GET /search/hybrid?q=<query>` depending on mode toggle
- `GET /embeddings/stats` on tab activation
- `POST /embeddings/reindex` when the Reindex button is clicked

**Crons tab**

No API calls; the tab renders a static list of Phase 2 planned cron jobs.

### D3 graph topology

`buildGraph()` constructs a force-directed graph with three node types and two link rules:

- **Conversation nodes** (`conv_<id>`, blue circles) — one per entry from `/conversation/recent`.
- **Memory nodes** (`mem_<id>`, green squares) — one per entry from `/memory/list`.
- **Entity nodes** (`ent_<word>`, orange rotated squares) — extracted from memory
  `description`/`content` by a naive regex (`/\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\b/g`); at most
  three entities per memory are resolved to nodes, with deduplication across memories via
  `entityMap`.

Link rules:

1. **Memory → Entity** — for every entity extracted from a memory node.
2. **Conversation → Memory** — when `c.channel === m.channel` (shared channel).

Simulation uses `d3.forceSimulation` with link, many-body charge, center, and collision forces.
Pan/zoom is provided by `d3.zoom`. Node drag is supported via `d3.drag`. Clicking a node
populates the `#side-panel` via `showDetail()`, which safely renders a table of node
attributes using the `escHtml()` helper throughout.

---

## 2. Security findings

### SRI-001 — D3 loaded from CDN without Subresource Integrity _(Medium)_

```html
<script src="https://d3js.org/d3.v7.min.js"></script>
```

No `integrity` attribute. If the CDN is compromised or the resource is MITM-replaced, the
browser will execute arbitrary JavaScript with full page access.

**Remediation:** Generate the SHA-384 hash of the known-good build and add an `integrity`
attribute, e.g.:

```html
<script
  src="https://d3js.org/d3.v7.min.js"
  integrity="sha384-<hash>"
  crossorigin="anonymous"
></script>
```

Use the [SRI Hash Generator](https://www.srihash.org/) or `openssl dgst -sha384 -binary d3.v7.min.js | openssl base64 -A`.

---

### CSP-001 — No Content-Security-Policy header or meta tag _(Medium)_

There is no `<meta http-equiv="Content-Security-Policy">` tag and no evidence of a
server-side CSP header. Because D3 is loaded from a CDN (`d3js.org`) and all other scripts
are inline, a CSP would need to permit at least that origin for `script-src`.

**Remediation:** Add a CSP delivered by the Flask server (preferred over meta tag, which does
not protect against injection in the HTTP response itself):

```python
@app.after_request
def add_csp(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://d3js.org; "
        "style-src 'self' 'unsafe-inline'; "   # inline styles are used
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response
```

Note that eliminating `'unsafe-inline'` for styles would require moving inline styles to an
external stylesheet — a worthwhile Phase 2 hardening step.

---

### XSS-001 — No XSS vectors found _(Informational)_

All `innerHTML` assignments are reviewed below:

| Assignment                                 | Dynamic source                                     | Escaping                          |
| ------------------------------------------ | -------------------------------------------------- | --------------------------------- |
| `sidePanelContent.innerHTML = html`        | API fields via `row()` helper                      | `escHtml()` on every value        |
| `header.innerHTML = ...` in renderLogs     | `date` from `toLocaleDateString()`, filtered count | `escHtml(date)`                   |
| `entryEl.innerHTML = ...` in renderLogs    | role, channel, timestamp, content preview          | `escHtml()` on all                |
| `ragResults.innerHTML = ...map().join('')` | score, role, channel, content                      | `escHtml()` on all                |
| `ragStatsBody.innerHTML = html`            | API keys and values                                | `escHtml()` on both key and value |
| Clearing assignments (`= ''`)              | —                                                  | n/a                               |

The `roleClass` variable (injected directly into a class attribute string) is sanitized by
allowlist: `['user', 'assistant', 'system'].includes(role) ? role : 'system'`, preventing
class-attribute injection.

**No XSS vectors are present in the current implementation.**

---

## 3. Correctness findings

### CORRECT-001 — `--topbar-h` CSS variable _(No bug)_

`setTopbarHeight()` is called synchronously at script parse time (script tag is at end of
`<body>`, so the topbar element is in the DOM and `offsetHeight` is available) and again on
every `window resize` event. The CSS fallback of `56px` in `:root` is overridden correctly.

### CORRECT-002 — Tab switching _(No bug)_

`activateTab()` manipulates only CSS classes; no `href` navigation occurs. Tab switching is
fully client-side and does not reload the page.

### CORRECT-003 — Graph builds both conversation and memory nodes _(No bug)_

`loadGraph()` calls both `/conversation/recent` and `/memory/list` in parallel and passes
both result arrays to `buildGraph()`, which iterates each to produce the node lists.

### CORRECT-004 — Error banner auto-dismisses _(No bug)_

`showError()` sets a 5-second `setTimeout` that hides the banner. `clearTimeout(errorTimer)`
before re-setting prevents multiple concurrent timers from stacking.

### CORRECT-005 — "Load more" replaces rather than appends _(Minor UX bug)_

`logsLimit` is incremented by 100 and `loadLogs()` is called, but `loadLogs()` does
`logsList.innerHTML = ''` before rendering. The effect is that all entries up to the new
limit are re-fetched and re-rendered from scratch. This is functionally correct but
inefficient for large datasets and does not preserve scroll position. Cursor-based
pagination with append-only rendering is deferred to Phase 2.

### CORRECT-006 — Reindex calls `POST /embeddings/reindex` _(No bug)_

```javascript
const data = await apiFetch("/embeddings/reindex", { method: "POST" });
```

This is correct.

### CORRECT-007 — Graph tab not lazy-loaded on first render _(Minor)_

The graph tab is pre-marked active in HTML (`class="tab-pane active"`) and `loadGraph()` is
called unconditionally at script end, bypassing the `onTabFirstActivate` lazy-load path
(which sets `tabActivatedOnce['graph'] = true` immediately). This is intentional and
correct, but means the graph always loads on page open regardless of user intent.

---

## 4. Accessibility findings

### A11Y-001 — Tab bar lacks ARIA roles _(Low)_

The tab buttons carry no `role="tab"`, `aria-selected`, or `aria-controls` attributes, and
the container has no `role="tablist"`. Screen readers will announce these as plain buttons
with no semantic relationship.

**Remediation:**

```html
<div role="tablist" aria-label="Navigation">
  <button
    role="tab"
    aria-selected="true"
    aria-controls="graph-pane"
    class="tab-btn active"
    data-tab="graph"
  >
    …
  </button>
  …
</div>
<div id="graph-pane" role="tabpanel" …>…</div>
```

`activateTab()` should toggle `aria-selected` on buttons and `aria-hidden` on panes.

### A11Y-002 — D3 graph nodes are not keyboard-focusable _(Low)_

SVG `<g>` elements receive click handlers but have no `tabindex` and no `role`. Graph nodes
cannot be navigated or activated via keyboard alone.

**Remediation (Phase 2):** Add `tabindex="0"` and `role="button"` to each node `<g>` during
D3 join, and attach `keydown` listeners for `Enter`/`Space` that trigger `showDetail()`.

### A11Y-003 — Dark theme CSS is correctly implemented _(Informational)_

All colors are expressed as CSS custom properties under `:root`, applied via `var()` throughout.
No hard-coded color values appear outside the `:root` block (with the minor exception of the
inline `style` attributes on legend dots, which reference `var()` expressions). The theme is
self-consistent and would support a future light-mode override via a single `:root` override block.

---

## 5. Known limitations (Phase 1, deferred to Phase 2)

- **No background cron jobs.** The Crons tab is informational only; all listed jobs
  (conversation summarization, importance rescoring, memory deduplication) are placeholders.
- **Naive entity extraction.** Entities are identified by a title-case regex, not NER. This
  produces false positives and misses multi-word or non-English entities.
- **Channel-only graph linking.** Conversation–memory edges are drawn only when
  `c.channel === m.channel`. No semantic or temporal proximity is considered.
- **No cursor-based pagination.** The Logs tab re-fetches from offset 0 on each "Load more"
  click, which becomes expensive as history grows.
- **No CSP or SRI.** See security findings CSP-001 and SRI-001.
- **No ARIA tab semantics.** See accessibility findings A11Y-001 and A11Y-002.
- **Inline styles prevent a strict CSP.** Moving inline `style` attributes and `<style>` blocks
  to an external stylesheet would allow removal of `'unsafe-inline'` from `style-src`.
