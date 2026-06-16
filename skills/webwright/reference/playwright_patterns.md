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
# Browser now exposes CDP on http://localhost:9222 (via .playwright/cli.config.json)
# Python scripts connect to the same browser with connect_over_cdp("http://localhost:9222")
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
- **Always** run `PWDEBUG=console` when launching the browser via
  `playwright-cli open`, or `window.playwright` will not be available.
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

## Python: connect to the same browser

While playwright-cli owns the browser, Python scripts connect via CDP:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.new_context(viewport={"width": 1280, "height": 1800})
    page = context.new_page()
    # ... interact with page ...
    browser.close()  # disconnects CDP client, browser stays alive
```

`browser.close()` only drops the Python CDP connection — the browser
process stays alive for playwright-cli to take over during self-healing.

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
# ⚠️ The confirm button may be in a different frame than the form.
# During exploration, use playwright-cli to identify which frame it lives in.
# Then reference the correct frame directly:
confirm_frame.get_by_role("button", name="确定").click()
# `confirm_frame` = the frame discovered during exploration (may be `frame`,
# `page`, or another `page.frame_locator()`). See `find_confirm_button()`
# helper below for the generic fallback pattern.
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

**Interaction flow (4 steps):**

```
Step 1: Click the trigger icon/button next to the field
        ↓
Step 2: Identify the popup iframe (name="lookupwindow" or similar)
        → Search keyword or directly select the target row
        → Select the target row
        → Verify row is highlighted/checked (screenshot!)
        ↓
Step 3: Click "确定" (Confirm) to close the popup and backfill
        ↓
Step 4: Verify the popup CLOSED (screenshot after)
        → If still open: a "请先选择数据" warning may have appeared.
          Dismiss it, ensure a row is selected, then click "确定" again.
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

# Confirm — the frame was determined during exploration (see below)
confirm_frame.get_by_role("link", name="确定").click()
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

# Confirm — the frame was determined during exploration (see below)
confirm_frame.get_by_role("link", name="确定").click()
```

**Key points:**
- The lookup popup is almost always an **iframe** — treat it with
  `page.frame_locator()`, never `page.locator("iframe").content_frame()`.
- **The "确定" confirm button is often NOT inside the lookup popup's
  iframe.** It typically resides in the parent frame or a sibling iframe.
  Always search across frames rather than assuming it's in the same one.
- **Verify the popup actually closed after clicking "确定".** If no data row
  was selected, the app may show a validation warning ("请先选择数据" /
  "Please select data first") instead of closing the popup. After clicking
  "确定", take a screenshot to confirm the popup disappeared. If it didn't:
  1. Check for and dismiss the validation warning (often a toast or a
     small alert near the bottom of the popup).
  2. Select the target data row, then click "确定" again.
- After confirmation, verify the backfilled value with a screenshot or
  by reading the field's `value` attribute.
- Some apps load the popup in a new browser window instead of an iframe —
  check `playwright-cli snapshot` for `f*` refs first; if none appear, look
  for a new page/tab.

### Discovery: which frame holds the confirm button?

During exploration, use `playwright-cli` to determine the correct frame for
the "确定" button — do NOT hard-code a cross-frame search loop in the final
script. The exploration phase already answers this question:

```bash
# 1. After the popup is open, snapshot the full page
playwright-cli snapshot --filename=popup_open.yaml

# 2. Search for "确定" in the YAML — note its ref prefix:
#    e123 → lives in the main frame (page)
#    f1e45 → lives in iframe #1 (frame.frame_locator("iframe").nth(1))
#    f2e67 → lives in iframe #2
```

Then in `final_script.py`, assign the correct frame object:

```python
# Determined during exploration — no loop needed:
confirm_frame = frame                         # if ref was e* (same frame)
# or
confirm_frame = page                          # if ref was e* (main frame)
# or
confirm_frame = page.frame_locator("iframe[name='lookupwindow']")  # if ref was f1*

confirm_frame.get_by_role("link", name="确定").click()
```

### Fallback: `find_confirm_button()` utility

If you absolutely need a generic fallback (rare — prefer exploration-driven
discovery), define this helper once at the top of the script:

```python
def find_confirm_button(page, frame, name="确定"):
    """Find a visible confirm button across all frames.
    
    Prefer exploration-driven discovery over this fallback.
    The correct frame should already be known from playwright-cli exploration.
    """
    for candidate in [frame] + page.frames:
        try:
            btn = candidate.get_by_role("link", name=name)
            if btn.is_visible():
                return btn
        except:
            continue
    raise RuntimeError(f"Could not find visible '{name}' button in any frame")

# Usage:
find_confirm_button(page, frame).click()
```

## Table Column Header-to-Cell Mapping

Before clicking any table cell, you **must** map header columns to data cell
indices. Clicking the wrong column is the most common table automation bug
and is invisible until you screenshot-verify.

### Mapping workflow

```
1. Snapshot the table page and locate the header row
2. List column index → column name:
    列0 → 对方性质
    列1 → 收款方    ← TARGET
    列2 → 收款户名
    列3 → 收款账号
3. In the data row, count cells from 0 to find the target cell
4. Confirm the cell ref matches the target column index
5. Click, then screenshot to verify the correct cell was activated
   (e.g. the correct cell should now show a textbox/search icon)
```

### Mapping template

During exploration, record the mapping in comments:

```python
# Column mapping: 0=对方性质 | 1=收款方 | 2=收款户名 | 3=收款账号 | ...
# Row: "内部员工 0.00 申请"
# Click cell[1] (收款方)
row.get_by_role("cell").nth(1).click()  # or use stable selector from eval
page.screenshot(path=str(SCREENSHOTS / "final_execution_N_click_payee.png"))
# Verify: read screenshot → confirm search icon / textbox appeared in the
# correct column, not an adjacent one
```

### Traps

- **Trap**: Seeing a row "内部员工 | 0.00 | 申请" and clicking the middle
  cell assuming it's the right column.
  **Fix**: Count cell indices from the header row first. Cell index 1 might
  be "收款方" while index 2 is "收款户名" — visually similar but different
  semantic columns.
- **Trap**: Using `get_by_role('row', name='...')` with Unicode icons in
  the row name.
  **Fix**: Row names often contain Unicode icon characters (`\ue113`,
  `\ue302`) that cause Python encoding errors. Use `get_by_text()` for the
  visible text portion instead.

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
        browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
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

        browser.close()  # disconnects CDP client; browser stays alive

if __name__ == "__main__":
    main()
```

Rules:
- **Always** set `viewport={"width": 1280, "height": 1800}`.
- **Never** call `page.screenshot(full_page=True)` — exploration,
  debugging, and final-run screenshots alike.
- Each script run creates a fresh browser context (new page, isolated
  cookies/storage) within the shared Chrome. Navigate from the start URL
  and reconstruct state in code.
- **Always call `browser.close()` at script end.** In CDP mode this only
  disconnects the Python client — the browser stays alive for playwright-cli
  to take over during self-healing.
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

The shared Chrome browser still has the page open at its failure state
after `final_script.py` calls `browser.close()`. No re-launch or
re-navigation is needed — playwright-cli is already attached:

1. **Re-snapshot** the current page (still alive in the shared Chrome):
   ```bash
   playwright-cli snapshot --filename=page_heal.yaml
   ```

2. **Re-eval** the selector for the target element:
   ```bash
   playwright-cli eval "(ele) => window.playwright.selector(ele)" <ref>
   ```

3. **Update `final_script.py`**: replace the failing selector with the
   fresh one from step 2. Use `Edit` for minimal changes.

4. **Re-run** inside `final_runs/run_<id+1>/` and re-verify all CPs.

The healing loop continues until all CPs pass or a hard blocker is confirmed.

## Never Force DOM / Never Use `force: true`

These are hard-unsafe patterns that produce brittle, unreliable scripts.
They are **always forbidden** in both exploration and final scripts.

### Forbidden operations

```python
# ❌ FORBIDDEN — NEVER use any of these:
element.click(force=True)                               # force:true
element.evaluate("el => el.removeAttribute('readonly')")  # JS DOM mutation
element.evaluate("el => el.value = 'xxx'")               # JS value injection
page.evaluate("document.querySelector(...).click()")      # JS click bypass
element.dispatch_event("click")                           # synthetic event
```

### What to do instead

**When an element is intercepted by another element (modal/overlay):**

```python
# ❌ WRONG: force-click through the overlay
page.get_by_role("button", name="保存").click(force=True)

# ✅ RIGHT: dismiss the overlay first, then click normally
# Preferred: the correct frame should already be known from exploration
# (see "Discovery: which frame holds the confirm button?" above).
# Use the generic loop below only as a last-resort fallback.
# Strategy 1: Find and click the visible confirm/close button
# The button might be in a DIFFERENT iframe than the current one!
# Try each iframe until you find the visible "确定" button:
for frame in page.frames:
    try:
        ok_button = frame.get_by_role("button", name="确定")
        if ok_button.is_visible():
            ok_button.click()
            break
    except:
        continue

# Strategy 2: If the overlay is a known modal class, scope within it
page.locator(".modal-overlay").get_by_role("button", name="取消").click()

# Strategy 3: Use keyboard to dismiss (if it responds to Escape)
page.keyboard.press("Escape")
```

**When a field is readonly and needs a lookup value:**

```python
# ❌ WRONG: remove the readonly attribute with JS
field.evaluate("el => el.removeAttribute('readonly')")
field.fill("some value")

# ✅ RIGHT: click the trigger icon that opens the lookup widget
field.locator("..").locator(".lee-icon").click()
# Then interact with the popup (see "Lookup Helper" section above)
```

**When multiple same-name buttons exist on the page:**

```python
# ❌ WRONG: unscoped selector may match the wrong "确定"
page.get_by_role("link", name="确定").click()

# ✅ RIGHT: scope to the visible popup/dialog container
page.locator(".lee-window").get_by_role("link", name="确定").click()
# Or find the visible one across iframes
for frame in page.frames:
    btn = frame.locator(".dialog-visible").get_by_role("button", name="确定")
    if btn.is_visible():
        btn.click()
        break
```

### Key principle

Always interact with the browser like a human user would:
- A human cannot `force: true` through an overlay — they dismiss it first.
- A human cannot `evaluate()` into a readonly field — they click the widget.
- A human sees which "确定" is on the active popup — scope selectors the same way.

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
