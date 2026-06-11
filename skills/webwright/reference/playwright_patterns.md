# Playwright Patterns

These are the canonical patterns the Webwright agent uses. Exploration is
driven by **playwright-cli** commands (not Python heredoc). The final
script uses **Python `sync_playwright`** with stable selectors obtained
from `window.playwright.selector()`.

## Exploration: playwright-cli command templates

All exploration is done with `playwright-cli`. Each command is atomic —
run one, observe its output, then decide the next step.

### Start browser and navigate

```bash
PWDEBUG=console playwright-cli open <START_URL> --headed
```

`PWDEBUG=console` injects `window.playwright` into the browser, enabling
the `window.playwright.selector()` API for stable element location.

### Take page snapshot (ARIA tree)

```bash
playwright-cli snapshot --filename=page.yaml
# Read page.yaml to discover element refs (e.g. e721)
```

The YAML snapshot lists all interactive elements with their refs, roles,
names, and hierarchy. Use this to find the elements you need.

**iframe element refs use a different prefix.** In the snapshot YAML:
- Top-level (main frame) elements use the `e` prefix: `e35`, `e721`
- Elements inside an iframe use the `f` prefix: `f4e8`, `f1e12`

The number after `f` identifies the iframe index; the part after that
identifies the element within that iframe. **You cannot pass an `f`-prefixed
ref directly to `page.click()` in `final_script.py`** — see the
"iframe Handling" section below for the correct approach.

### Take screenshot

```bash
playwright-cli screenshot --filename=screenshots/explore_1.png
```

### Get stable selector for an element

```bash
playwright-cli eval "(ele) => window.playwright.selector(ele)" e721
# Output example: get_by_role('button', {name: 'Filters'})
```

`window.playwright.selector()` returns a **semantic, stable locator
string** — much more robust than CSS classes or XPaths. This is the
selector you embed directly into `final_script.py`.

### Interact with elements

```bash
playwright-cli click e721
playwright-cli fill e722 "search term"
playwright-cli type e723 "text"
playwright-cli press Enter
```

### Inspect after interaction

```bash
playwright-cli snapshot --filename=page_after.yaml
playwright-cli screenshot --filename=screenshots/explore_after.png
# Read both snapshot and screenshot to verify the action succeeded
```

## Stable selector workflow

For every element that `final_script.py` will interact with:

```
1. playwright-cli snapshot --filename=page.yaml
2. Read page.yaml → identify target ref (e.g. e721)
3. playwright-cli eval "(ele) => window.playwright.selector(ele)" e721
4. Record the output (e.g. "get_by_role('button', {name: 'Filters'})")
5. playwright-cli click e721  ← verify the selector works
6. playwright-cli screenshot --filename=screenshots/verify.png
7. Read screenshot → confirm the interaction succeeded
```

Record all selector mappings so the final script authoring is
straightforward: copy each stable selector directly into the Python code.

Rules:
- **Always** run `PWDEBUG=console` when launching the browser, or
  `window.playwright` will not be available.
- **Always** verify the selector with an actual click/fill before adding
  it to the final script.
- **Always** take a before/after screenshot pair to confirm the
  interaction visually.

## Target elements with the stable selector

The output of `window.playwright.selector()` is a Playwright locator
string. Use it directly in Python:

```python
# From: playwright-cli eval "(ele) => window.playwright.selector(ele)" e721
# Output: get_by_role('button', {name: 'Filters'})
page.get_by_role("button", name="Filters").click()

# From: playwright-cli eval "(ele) => window.playwright.selector(ele)" e722
# Output: get_by_role('textbox', {name: 'Search'})
page.get_by_role("textbox", name="Search").fill("term")
```

If a selected state becomes hidden after a drawer/dropdown closes, reopen
it before capturing the verification screenshot.

**⚠️ iframe scope warning.** `window.playwright.selector()` returns an
*iframe-relative* selector when called on an `f`-prefixed element — it does
**not** include the iframe's own location. Using that selector on `page`
will time out. You must first obtain a `FrameLocator`, then chain the
selector on it. See the "iframe Handling" section below.

## iframe Handling

Many enterprise web apps (SAP, Yonyou, Kingdee, etc.) load functional
modules inside `<iframe>` elements. The exploration and scripting workflow
requires special handling for these pages.

### How iframe elements appear in snapshots

When the page contains iframes, the YAML snapshot uses two different ref
prefixes:

```yaml
# Main frame element — "e" prefix
- e35 [button] 'Login'

# iframe #4 inner element — "f4" prefix, then element ref "e8"
- f4e8 [link] 'Save'
```

- **`e` prefix** → top-level element. Works with `playwright-cli` commands
  directly (`click e35`, `eval ... e35`).
- **`f<iframeIdx>e<elementRef>` prefix** → element inside an iframe.
  `playwright-cli` can interact with these (`click f4e8`), but the stable
  selector returned by `window.playwright.selector()` is *iframe-relative*.

### Getting stable selectors for iframe elements

```bash
playwright-cli eval "(ele) => window.playwright.selector(ele)" f4e8
# Output: get_by_role('link', {name: 'Save'})
```

The returned selector is **relative to the iframe**, not the top-level page.
Using `page.get_by_role('link', name='Save')` will **time out** because
`page` only searches the main frame.

### Correct: use FrameLocator in final_script.py

```python
# ✅ Correct: obtain a FrameLocator, then chain the selector
frame = page.frame_locator("iframe").nth(1)  # select by index
# Or filter by name/src:
# frame = page.frame_locator("iframe[name='contentFrame']")
frame.get_by_role("link", name="Save").click()

# ❌ Wrong: using page directly for iframe content
page.get_by_role("link", name="Save").click()  # TimeoutError!

# ❌ Wrong: Locator → content_frame() does NOT exist
iframe = page.locator("iframe").nth(1)
frame = iframe.content_frame()  # AttributeError!
```

**Key API distinction:**

| Expression | Returns | Purpose |
|---|---|---|
| `page.locator("iframe")` | `Locator` | The iframe DOM element itself |
| `page.frame_locator("iframe")` | `FrameLocator` | The iframe's inner content context |

Always use `page.frame_locator()` to interact with elements **inside** an
iframe. `FrameLocator` supports all the same locator methods (`get_by_role`,
`get_by_text`, `locator(...)`, etc.) as `Page`.

### iframe screenshots

`FrameLocator` does not have a `.screenshot()` method. For verification
during the final script, use `page.screenshot()` — the iframe content will
be visible as part of the full page capture.

If you need a precise crop of just the iframe content:

```python
page.frame_locator("iframe").nth(1).locator("body").screenshot(
    path=str(SCREENSHOTS / "iframe_content.png")
)
```

### iframe exploration checklist

During exploration, when you encounter an iframe-heavy page:

1. Run `playwright-cli snapshot` and note all `f`-prefixed refs.
2. For each `f`-prefixed element you need, run `eval` to get its
   iframe-relative stable selector.
3. Identify which iframe index the element lives in (the number after `f`).
4. In `final_script.py`, always pair `page.frame_locator()` with the
   iframe-relative selector — never use `page` directly.

## Complex form interactions

Some web apps use non-standard form controls that require multi-step
interaction patterns beyond simple `fill()` / `click()`.

### Multi-language / popup input dialogs

Clicking a field may open a secondary dialog (e.g. a multi-language input
editor). You must interact with the dialog controls, then confirm:

```python
# Step 1: Open the popup editor
frame.locator(".lee-icon").first.click()

# Step 2: Fill content in the popup
frame.locator(".lee-text-field").fill("测试名称")

# Step 3: Confirm/close the popup
frame.get_by_role("button", name="确定").click()
```

### General pattern for complex controls

1. Click the visible control to open the secondary UI.
2. Locate and interact with the inner fields (use snapshot to discover refs).
3. Confirm or close the secondary UI.
4. Take a screenshot to verify the value was accepted.

These patterns require exploration with `playwright-cli snapshot` at each
sub-step to discover the correct element refs and selectors.

### Lookup Helper / Help Input Controls

Many enterprise web apps (SAP BYD, Yonyou, Kingdee, etc.) use **lookup
(help-input) controls** — a read-only text field paired with a trigger
button that opens a popup/dialog for value selection. The selected value
is then backfilled into the field. These controls require multi-dimensional
recognition because no single DOM attribute reliably identifies them.

**Recognition dimensions (match any one):**

| Dimension | Signal | Example |
|---|---|---|
| DOM attribute | `for="lookup_*"` or `id="lookup_*"` | `id="lookup_45537"` |
| DOM attribute | class contains `popup` | `.lee-popup`, `.popup-trigger` |
| Visual marker | Three dots `...` at field's right side | `.lee-ion-android-more-horizontal` icon |
| Visual marker | Special unicode icon at field's right side | `` or similar glyph |
| Behavioral | Field is `readonly` + adjacent element has `cursor: pointer` | clickable icon next to input |

**Interaction flow (3 steps):**

```
Step 1: Click the trigger icon/button next to the field
        ↓
Step 2: Identify the popup iframe (name="lookupwindow" or similar)
        → Search keyword or directly select the target row
        → Select the target row
        ↓
Step 3: Click "确定" (Confirm) to close the popup and backfill
```

**Discovering lookup controls during exploration:**

```bash
# 1. Snapshot the form page
playwright-cli snapshot --filename=form.yaml

# 2. Search snapshot for popup/lookup/iframe keywords
# 3. Identify the trigger button ref next to the lookup field
# 4. Click the trigger button
playwright-cli click <icon_ref>

# 5. Re-snapshot to find popup/iframe content elements
playwright-cli snapshot --filename=popup_content.yaml

# 6. Look for newly appeared f*-prefixed elements (iframe content)
# 7. Get stable selectors for popup elements
playwright-cli eval "(ele) => window.playwright.selector(ele)" <f_ref>
```

**Script code templates:**

```python
# Method 1: class contains popup
frame.locator(".lee-popup-trigger").first.click()

# Method 2: three-dots icon at field's right side
frame.locator(".lee-icon.lee-ion-android-more-horizontal").first.click()

# Method 3: lookupwindow iframe (most general)
popup_frame = frame.frame_locator("iframe[name='lookupwindow']")
popup_frame.get_by_title("Target Row Text").click()

# Confirm selection
frame.get_by_role("link", name="确定").click()
```

If the popup provides a search field before row selection:

```python
# Open lookup popup
frame.locator(".lee-popup-trigger").first.click()

# Search inside the popup iframe
popup_frame = frame.frame_locator("iframe[name='lookupwindow']")
popup_frame.get_by_role("textbox").fill("search keyword")
popup_frame.get_by_role("button", name="搜索").click()

# Select result row
popup_frame.get_by_title("Target Row Text").click()

# Confirm
frame.get_by_role("link", name="确定").click()
```

**Key points:**
- The lookup popup is almost always an **iframe** — treat it with
  `page.frame_locator()`, never `page.locator("iframe").content_frame()`.
- After confirmation, verify the backfilled value with a screenshot or
  by reading the field's `value` attribute.
- Some apps load the popup in a new browser window instead of an iframe —
  check `playwright-cli snapshot` for `f*` refs first; if none appear, look
  for a new page/tab.

## Prefer interactive form filling over deep-link URLs

When a task requires parameterizing a search (locations, dates, filters,
query strings), **drive the on-page form interactively** rather than
constructing a deep-link URL. Deep links are brittle:

- Sites silently drop parameters they cannot parse.
- URL parsers vary by locale, A/B bucket, and signed-in state.
- A working deep link for one input tells you nothing about whether
  another set will populate.

Interactive filling using the same controls a human would click is the
most reliable strategy. Use `playwright-cli` to find the controls, get
their stable selectors, then embed them in the final script.

## Final-script instrumentation (sync_playwright)

`final_runs/run_<id>/final_script.py` must:

- write to `final_runs/run_<id>/screenshots/final_execution_<step>_<action>.png`,
- reset and append to `final_runs/run_<id>/final_script_log.txt`,
- print the final datum at the end of the log.

```python
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

RUN_DIR = Path(__file__).parent
SCREENSHOTS = RUN_DIR / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
LOG = RUN_DIR / "final_script_log.txt"
LOG.write_text("")  # reset

def log(step: int, msg: str) -> None:
    line = f"step {step} action: {msg}\n"
    with LOG.open("a") as f:
        f.write(line)
    print(line, end="")

def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 1800})
        page = context.new_page()

        page.goto("<START_URL>", wait_until="domcontentloaded")
        page.screenshot(path=str(SCREENSHOTS / "final_execution_1_open_start_page.png"))
        log(1, "open start page")

        # Each interaction uses the stable selector from playwright-cli:
        # playwright-cli eval "(ele) => window.playwright.selector(ele)" e721
        # → page.get_by_role("button", name="Filters")
        page.get_by_role("button", name="Filters").click()
        page.screenshot(path=str(SCREENSHOTS / "final_execution_2_open_filters.png"))
        log(2, "open filter panel")

        # ... more CP steps ...

        # End of run: capture final datum
        final_value = "<extracted price / code / winner>"
        with LOG.open("a") as f:
            f.write(f"\nFINAL_RESPONSE: {final_value}\n")

        browser.close()

if __name__ == "__main__":
    main()
```

Rules:
- **Always** set `viewport={"width": 1280, "height": 1800}`.
- **Never** call `page.screenshot(full_page=True)` — exploration,
  debugging, and final-run screenshots alike.
- Each Playwright run is fresh: navigate from the start URL, reapply
  filters, reconstruct state in code. There is no persistent session.
- Script stays simple: each element uses the single stable selector from
  `window.playwright.selector()`, no fallback arrays or wrapper functions.

## Agent Loop self-healing

When the final script fails (element not found, timeout, CP verification
fails), the agent does NOT hand-edit selectors by guessing. Instead:

### Trigger conditions

- `final_script.py` raises an exception (element not found, timeout, etc.)
- Self-verify finds a CP not satisfied (element not visible, page state
  doesn't match expectations)
- Page URL did not change as expected
- Expected element not present in after screenshot

### Healing flow

1. **Re-open the page** using playwright-cli:
   ```bash
   PWDEBUG=console playwright-cli open <URL> --headed
   ```

2. **Re-navigate** to the state where the failure occurred (repeat the
   interactions that worked, up to the failing step).

3. **Re-snapshot** the page at the failure point:
   ```bash
   playwright-cli snapshot --filename=page_heal.yaml
   ```

4. **Re-eval** the selector for the target element:
   ```bash
   playwright-cli eval "(ele) => window.playwright.selector(ele)" <ref>
   ```

5. **Update `final_script.py`**: replace the failing selector with the
   fresh one from step 4. Use `Edit` for minimal changes.

6. **Re-run** inside `final_runs/run_<id+1>/` and re-verify all CPs.

The healing loop continues until all CPs pass or a hard blocker is confirmed.

## Inspection commands

```bash
# Latest run tree + log
ls -R final_runs/run_<id>
cat final_runs/run_<id>/final_script_log.txt

# Quick file read
sed -n '1,50p' final_runs/run_<id>/final_script.py
```

For visual checks, use the `Read` tool on individual PNG files inside
`final_runs/run_<id>/screenshots/`.
