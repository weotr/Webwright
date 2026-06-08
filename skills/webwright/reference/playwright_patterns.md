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
