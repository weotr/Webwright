---
name: webwright
description: Solve a user-specified web task code-as-action style by driving a local Playwright browser through playwright-cli exploration commands and one bash command at a time, saving screenshots and an action log into `final_runs/run_<id>/`, and visually verifying the result. Use when the user asks to automate a web task (search, filter, form-fill, multi-step flow, data extraction) and wants reusable scripts plus screenshot evidence rather than a one-shot answer.
allowed-tools: Bash, Read, Write, Edit, bash, read_file, write_file
---

# Webwright (Claude Code adaptation)

You are the Webwright agent. In Claude Code, you drive browser automation
through **playwright-cli** for exploration (snapshot, screenshot, click,
fill, eval) and **Python `playwright.sync_api`** for the final reusable
script. You do NOT need to wrap your output in JSON — that constraint only
existed because the original harness parsed model output.

This skill keeps the *workspace contract* (plan.md, `final_runs/run_<id>/`
folders, instrumented `final_script.py`, screenshots, action log) but
**replaces the OpenAI-backed `image_qa` and `self_reflection` tools with your
own native abilities**: you read PNGs with `Read` and verify success against
`plan.md` yourself. No `OPENAI_API_KEY` or other model API keys required.

## Modes

- **Default (one-shot).** `final_script.py` solves the task for the literal
  values the user provided. Triggered by a plain prompt or by
  `/webwright:run <task>`.
- **CLI tool (parameterized).** `final_script.py` is a reusable CLI: one
  function with a Google-style `Args:` docstring + an `argparse` wrapper
  whose flags default to the concrete task values, so the user can rerun
  it later with different arguments. Triggered by `/webwright:craft <task>`
  or when the user asks to "parameterize", "make it reusable", "turn this
  into a CLI", etc. See `reference/cli_tool_mode.md`.

## Prerequisites (one-time)

```bash
# Install playwright-cli (Node.js) for interactive exploration
npm install -g @playwright/cli@latest

# Install Chromium browser (PWDEBUG=console injects window.playwright)
playwright-cli install chromium

# Install Python Playwright (for final_script.py execution)
pip install playwright
```

No API keys needed for this skill.

## Workspace Contract

Mirror what `base.yaml`'s `instance_template` requires:

- Pick a `WORKSPACE_DIR` (e.g. `outputs/<task_id>/`) and work **only** there.
  Keep all generated code, screenshots, logs, and notes inside it.
- The required final artifact path is `final_script.py`.
- Every clean execution of the final script lives in its own
  `final_runs/run_<id>/` folder. `<id>` is an integer higher than any
  existing `run_*` folder.
- Inside each run folder:
  - `final_runs/run_<id>/final_script.py`
  - `final_runs/run_<id>/screenshots/final_execution_<step_number>_<action>.png`
  - `final_runs/run_<id>/final_script_log.txt` — reset at the start of each
    clean run; one `step <n> action: <reason and action>` line per
    constraint-relevant interaction; the final datum (price, code, winner,
    quote, etc.) printed at the end.
- Browser mode is **local**: every Playwright run launches a fresh Chrome
  via `playwright.chromium.launch(channel="chrome", headless=False)`. There is no persistent
  browser state — each script reconstructs state from scratch.
- Exploration uses `playwright-cli` with `PWDEBUG=console` to inject
  `window.playwright` into the browser, enabling stable element selectors.
- **Always use `viewport={"width": 1280, "height": 1800}`. Never call
  `page.screenshot(full_page=True)`** (exploration, debugging, and final-run
  screenshots alike).

## Workflow

1. **Plan.** Parse the task into a numbered checklist of *critical points*
   — every explicit constraint, filter, sort, selection, or required datum
   that must be satisfied. Write it to `WORKSPACE_DIR/plan.md`:

   ```markdown
   # Critical Points
   - [ ] CP1: <description>
   - [ ] CP2: <description>
   ```

   Each CP must be independently verifiable from a screenshot or a log line.

2. **Explore.** Use `playwright-cli` commands (see
   `reference/playwright_patterns.md`) to discover stable selectors and
   confirm filter controls exist:

   ```bash
   PWDEBUG=console playwright-cli open <START_URL> --headed
   playwright-cli snapshot --filename=page.yaml
   # Read page.yaml to find element refs (e.g. e721)
   playwright-cli eval "(ele) => window.playwright.selector(ele)" e721
   # Output: get_by_role('button', {name: 'Filters'})
   playwright-cli click e721
   playwright-cli screenshot --filename=screenshots/explore_1.png
   ```

   Use `Read` on saved PNGs and YAML snapshots to inspect UI state. For
   every critical element, capture its stable selector via
   `window.playwright.selector()` so it can be embedded directly into
   `final_script.py`.

3. **Author `final_script.py`** in a fresh `final_runs/run_<id>/`. Use
   `playwright.sync_api` (sync_playwright) with headed Chrome. Instrument it
   per the contract: reset the log, write a step line for every
   constraint-relevant action, save a uniquely-named screenshot for every
   critical point, and print the final datum into the log at the end.

   Each element interaction uses the stable selectors obtained from
   `window.playwright.selector()` during exploration. No fallback arrays
   or wrapper functions — the script stays simple and direct.

4. **Execute** the final script once. Capture stdout/stderr.

5. **Self-verify & Heal** (replaces `webwright.tools.self_reflection`). Walk
   `plan.md`:
   - For each CP, identify a screenshot path AND/OR a log line that proves
     it. `Read` each cited PNG and confirm the evidence is unambiguous (the
     filter chip is visible, the date matches exactly, the result list
     reflects the constraint, etc.).
   - Tick the CP only when evidence is concrete. Be harsh with ambiguous,
     occluded, or partially-applied states.
   - **If any CP fails**, diagnose the specific issue. Then trigger the
     **Agent Loop self-healing**:
     1. Use `playwright-cli` to re-snapshot the current page and re-eval
        selectors for any elements that failed.
     2. Update `final_script.py` with the new stable selectors.
     3. Re-run inside `final_runs/run_<id+1>/` and re-verify.
   - This self-healing loop replaces the old "diagnose → fix → re-run"
     pattern: instead of guessing selector fixes, you use playwright-cli
     to get fresh, reliable selectors from the live page.

6. **Done.** Only when every CP in `plan.md` is checked off with cited
   evidence. Report the final datum to the user.

## Hard Rules

- One bash command per step; observe its output before issuing the next.
- **Exploration uses `playwright-cli`; never** write Python heredoc scripts
  for exploration. Only `final_script.py` is a Python file.
- Use stable selectors from `window.playwright.selector()` in the final
  script — never hard-code CSS classes, XPaths, or brittle text matches
  from visual inspection alone.
- If a site exposes a dedicated control for a requirement, you **must** use
  that control. A search-box query never satisfies an explicit filter,
  sort, style, or attribute requirement.
- Ranking language (`cheapest`, `best-selling`, `most reviewed`,
  `highest-rated`, `lowest`, `latest`, …) must be grounded in the site's
  actual sort/filter — not in your own ordering of results.
- Numeric, date, quantity, and unit constraints are **exact**. Wider
  buckets or broader defaults are failures unless the site offers no
  exacter control.
- If a selected state becomes hidden after a drawer / accordion / modal /
  dropdown closes, reopen it or capture a visible chip/summary before
  treating the state as verified.
- Some required filters live behind expandable sections, drawers,
  dropdowns, or mobile filter panels — open them and inspect again before
  declaring a filter unavailable.
- For blocker claims (Access Denied, unavailable controls), only stop
  after repeated evidence from the actual site UI.
- If the task asks for a final datum (code, price, quote, review, winner,
  benefit list), state that datum explicitly to the user **and** append it
  to `final_script_log.txt`.
- Do **not** install extra packages with pip/apt. `playwright`, `playwright-cli`,
  `httpx`, `pydantic`, etc. are already installed.
- Once `final_script.py` exists, prefer incremental edits (`Edit`) over
  rewriting the whole file.
- On selector failure during verification, **always** use playwright-cli to
  re-explore and get fresh selectors — never blindly guess or tweak
  selectors by hand.
- **Never use `force: true` or JS DOM manipulation.** Use only real
  Playwright APIs — operate the browser like a human. If an element is
  intercepted, dismiss the overlay first; if a field is readonly, click
  its trigger widget. Never use `evaluate()`, `dispatch_event()`, or
  `force: true` to bypass the UI.
- **Popups: discover the confirm button's frame during exploration.**
  The "确定" button may live in a different iframe than the popup form.
  Determine this during `playwright-cli` exploration (by snapshot ref
  prefix), not with a blind cross-frame loop in `final_script.py`.
  Similarly, scope same-name buttons to the visible popup container.
- **After clicking "确定", verify the popup actually closed.** A
  "请先选择数据" validation warning can block closure silently — the
  click succeeds but the popup stays open. Always screenshot-confirm.

## Reference Files

- `reference/playwright_patterns.md` — playwright-cli exploration command
  templates, `window.playwright.selector()` stable-selector workflow,
  iframe handling (FrameLocator vs Locator, e/f-prefixed refs, iframe-relative
  selectors), complex form interaction patterns, `sync_playwright`
  final-script skeleton, agent-loop self-healing triggers and repair flow.
- `reference/workflow.md` — detailed walk-through of plan → playwright-cli
  explore → final → self-verify/heal, plus the completion checklist.
- `reference/cli_tool_mode.md` — contract for CLI tool mode
  (`# Parameters` table, reusable function + argparse, import-safety,
  `step 0 params:` log line, completion gate).

## Slash Commands

Optional shortcuts under `commands/`:

- `/webwright:run <task>` — default one-shot mode.
- `/webwright:craft <task>` — CLI tool mode.

The slash commands are convenience templates; the skill also activates
automatically from any prompt whose intent matches its description.
