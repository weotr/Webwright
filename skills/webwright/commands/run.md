---
description: Run a one-shot web task with the Webwright Playwright workflow.
argument-hint: <natural-language web task>
---

You are operating as the Webwright agent. Solve the following web task
code-as-action style by driving a local Playwright browser through
playwright-cli for exploration and Python `sync_playwright` for the
final script, saving screenshots and an action log into
`final_runs/run_<id>/`, and visually verifying the result.

Task:

$ARGUMENTS

For the full operating contract, first read the `SKILL.md` of the
`webwright` skill (the parent directory of this `commands/` folder).
Then follow the standard Webwright workflow:

1. Pick a `WORKSPACE_DIR` and write `plan.md` with a numbered list of
   critical points.
2. Explore with `playwright-cli` commands (`PWDEBUG=console`, snapshot,
   eval `window.playwright.selector()`, click, fill, screenshot). Use
   `Read` on PNGs and YAML snapshots to inspect UI state.
3. Author and run an instrumented `final_script.py` inside a fresh
   `final_runs/run_<id>/` using `sync_playwright` (viewport 1280×1800,
   headless Chromium, no `full_page=True`). Each element uses the
   stable selector from `window.playwright.selector()` — no fallback
   arrays.
4. Self-verify every critical point against the saved screenshots and
   `final_script_log.txt`. On failure, trigger agent-loop self-healing:
   re-explore with playwright-cli, get fresh selectors, update the
   script, re-run in a new `run_<id+1>/`. Repeat until every CP is
   ticked with cited evidence.
5. Report the final datum (price, code, winner, …) verbatim.

Refer to `reference/playwright_patterns.md` and `reference/workflow.md`
(under the same skill directory) for details. Do **not** use CLI tool
mode for this task.
