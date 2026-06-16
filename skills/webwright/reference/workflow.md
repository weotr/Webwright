# Workflow

Detailed expansion of the six-step Webwright loop, adapted for playwright-cli
exploration with agent-level self-healing. The original loop relied on
`webwright.tools.image_qa` for visual QA and `webwright.tools.self_reflection`
for the final verdict. Both are replaced here by your native abilities
(`Read` on PNG files + reasoning against `plan.md`). No `OPENAI_API_KEY`
is required.

## 1. Plan

Parse the task into critical points (CPs) and write `WORKSPACE_DIR/plan.md`:

```markdown
# Task
<verbatim task description>

# Critical Points
- [ ] CP1: <constraint / filter / sort / selection / required datum>
- [ ] CP2: ...
```

Rules for CPs:

- One CP per independently verifiable requirement.
- Numeric, date, quantity, and unit CPs must be exact.
- Ranking CPs ("cheapest", "best-selling", "highest-rated", …) must
  reference the site's actual sort/filter control.
- If the task asks for a final datum, make it its own CP
  (e.g. `CP5: Record the displayed cheapest economy fare`).

## 2. Explore

Goal: discover interactive controls, confirm every required filter exists,
and get stable selectors via `window.playwright.selector()` for each
element the final script will interact with.

- Use `playwright-cli` commands (one per step, see `playwright_patterns.md`):
  ```bash
  PWDEBUG=console playwright-cli open <URL> --headed
  # Browser is now on CDP http://localhost:9222 (via .playwright/cli.config.json)
  playwright-cli snapshot --filename=page.yaml
  ```
- Read the YAML snapshot to identify element refs (e.g. e721).
- For each target element, get its stable selector:
  ```bash
  playwright-cli eval "(ele) => window.playwright.selector(ele)" e721
  # Output: get_by_role('button', {name: 'Filters'})
  ```
- Verify the selector works with an actual click/fill and a screenshot:
  ```bash
  playwright-cli click e721
  playwright-cli screenshot --filename=screenshots/verify_control.png
  ```
- Read screenshots to confirm UI state when the snapshot description is
  ambiguous.
- If a filter looks unavailable, expand drawers / accordions / mobile
  filter panels and inspect again before concluding it doesn't exist.
- A search-box query never substitutes for a dedicated filter control.
- Save scratch screenshots under `WORKSPACE_DIR/screenshots/` (separate
  from `final_runs/`).

## 3. Author `final_script.py`

Create a fresh `final_runs/run_<id>/` (use the next integer above any
existing `run_*`) and place `final_script.py` inside it. Instrument per
`playwright_patterns.md`:

- viewport 1280×1800, connect to shared Chrome via
  `connect_over_cdp("http://localhost:9222")` and `sync_playwright`, no
  `full_page`;
- each element interaction uses the single stable selector from
  `window.playwright.selector()` — no fallback arrays;
- one `final_execution_<step>_<action>.png` per CP;
- one `step <n> action: <reason and action>` log line per
  constraint-relevant interaction;
- the final datum printed into `final_script_log.txt` at the end.

Each screenshot should map to a CP from `plan.md` so verification is
trivial.

## 4. Execute

Run the script once. If it crashes, fix it inside the same run folder and
re-execute — but if a partial run already produced screenshots that don't
match the fixed flow, delete them so the run folder reflects a single
clean execution.

## 5. Self-verify & Heal (replaces `self_reflection`)

For every CP in `plan.md`:

1. Identify the screenshot(s) and/or log line that provide evidence.
2. `Read` each cited PNG.
3. Confirm the evidence is **unambiguous**:
   - Filter chip / selected state visibly applied (not hidden behind a
     closed drawer);
   - Numeric / date values match exactly (not broadened);
   - Sort applied via the site's control (not implied by result order);
   - Required submit / search / apply action visibly taken;
   - Final datum legibly displayed.
4. Tick the CP only when the evidence is concrete. Be harsh on partial,
   occluded, or ambiguous states.

**If any CP fails → trigger Agent Loop self-healing:**

### Heal sub-steps

1. **Diagnose** the specific issue — wrong filter value, missing control,
   hidden chip, broadened range, selector failure, missing confirmation,
   missing screenshot, etc.
2. **Re-explore** the failure point with playwright-cli. The shared
   Chrome is still running with the page at its failure state — no
   re-launch or re-navigation needed:
   ```bash
   playwright-cli snapshot --filename=page_heal.yaml
   ```
3. **Re-eval** the failing element's selector:
   ```bash
   playwright-cli eval "(ele) => window.playwright.selector(ele)" <ref>
   ```
4. **Update `final_script.py`** with the fresh selector (use `Edit` for
   minimal changes — do NOT rewrite the whole file).
5. **Re-run** inside `final_runs/run_<id+1>/` and re-verify all CPs
   against `plan.md`.

The healing loop repeats until all CPs pass or a hard blocker is
confirmed with repeated evidence from the actual site UI.

Empty result sets are acceptable when the correct filters were
demonstrably applied.

## 6. Done

Stop only when **all** of the following are true:

1. `plan.md` exists with every CP enumerated as a checklist item.
2. `final_runs/run_<id>/final_script.py` ran cleanly from scratch and
   produced `final_script_log.txt` plus all CP screenshots.
3. Every CP is checked off with a cited screenshot and/or log line.
4. The final datum (if the task asked for one) is reported to the user
   verbatim and is also present in `final_script_log.txt`.
5. `ls -R final_runs/run_<id>` and `cat final_runs/run_<id>/final_script_log.txt`
   show the expected artifacts.

If any of those is false, do not declare done — trigger the Heal
sub-steps (Section 5), fix, and re-run in a new `run_<id+1>/`.
