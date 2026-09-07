# Agent Development Protocol

You are working on **UPVN**, a Ren'Py-inspired VN framework for UPBGE.
Story script (`.rpy`) and extension code (`.py`) are **separate** — no `python:` blocks in scripts.

## Before coding

1. Read `ROADMAP.md` — find the first `todo`/`in_progress` with dependencies `done`.
2. Read `COMMAND_SPEC.md` + `SCRIPT_LANGUAGE_SPEC.md`.
3. Read the relevant `examples/NN_*/expected_behavior.md`.
4. Check existing tests (`pytest tests/ -k exNN`).
5. Identify smallest missing feature for that milestone (one command or one UI piece).

## When coding

1. **Do not rewrite unrelated systems.** Keep `engine/core` pure-Python where possible.
2. Add or update tests (`tests/test_*.py`).
3. Keep script syntax compatible with `SCRIPT_LANGUAGE_SPEC.md` (Ren'Py-subset, no YAML leak).
4. Preserve existing example projects — they are contracts/goldens.
5. Errors must be friendly: `file:line:col message` + `Hint:` + caret line, no leaked tracebacks to authors.
6. Any feature must be exercised by an example game — untested features rot.
7. Every third milestone, do a **refactor pass**: deduplicate, update SPECs, run all examples.

## Trace tests gate merges; screenshots inform humans

- `engine/` must run **headless** (`VNController.run_headless(choices=…)`) and emit an event trace.
- Tests compare traces to golden JSON (`tests/data/trace_*.json`).
- UPBGE rendering (`bge_frontend/`) just consumes those same events visually.
- Never invert this: traces are CI; screenshots are for human review via `bge.render.makeScreenshot`.

## After coding

1. Run `pytest` if possible. Earlier examples must stay green (regression).
2. Update `CHANGELOG.md` with what changed.
3. Update `STATUS.md`:
   ```
   Last completed: TASK-XXX
   Currently failing: example NN
   Recommended next task: TASK-YYY
   Notes: indent is 4 spaces, etc.
   ```
4. If you finish a roadmap item, flip its `status` in `ROADMAP.md` to `done`.
5. If blocked >2 attempts, append blocker to `DECISIONS.md`, create a reduced sub-milestone, continue.

## Definition of done (for a command)

- Parses good example: `parse_string("show ...")` → AST node.
- Bad example: `parse_string("jump foo:")` → `ParseError` with hint `remove colon`.
- Interpreter: `run_headless` trace matches golden.
- If UPBGE-related: `blend/UPVN_Template.blend` demonstrates it when you press P.
- Docs updated: `COMMAND_SPEC.md` entry + `examples/XX/README.md`.

## .rpy authoring rules you must enforce

- No `init python`, no `python:` blocks, no `$` with arbitrary calls — only `$ var op expr`.
- State must be declared (`default foo = 0`) — no implicit globals.
- Project manifest is explicit (future `project.upvn.toml`), don't scan whole folder and execute orphan `.rpyc` (see `docs/renpy_criticism.md`).
- Saves are JSON, not pickle — only JSON/MessagePack-compatible state.
- Screens are pure functions of `VNState` (immediate-mode, reactive), no prediction pre-runs, no `restart_interaction`.

## Prompt template for subtasks

```
You are implementing UPVN.
Read: ROADMAP.md, COMMAND_SPEC.md, SCRIPT_LANGUAGE_SPEC.md, examples/01_branching_choice/expected_behavior.md
Task: Implement jump + menu (TASK-052/053)
Constraints: don't rewrite unrelated, preserve ex00, add tests, invalid jump raises ScriptRuntimeError with label name, update CHANGELOG.
Done when: ex00 tests green, ex01 both choice paths trace-match, manual UPBGE reaches both endings.
```
