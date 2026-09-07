# Expected Behavior — Example 05 (declarative script)

This example proves the **declarative** script forms parse to the *same* AST
and produce the *same* trace as the legacy Ren'Py-like forms
(`define`/`default`/`$`/bare `"choice":`).

## Language forms exercised

| Declarative form                      | Equivalent legacy form                     |
| -------------------------------------- | ------------------------------------------ |
| `state:` + `affection: int = 0`        | `default affection = 0`                    |
| `character e:` + `name` / `color`      | `define e = Character("Eileen", color=…)` |
| `set affection += 1`                   | `$ affection += 1`                         |
| `choice "Help Eileen":` inside `menu:` | `"Help Eileen":` inside `menu:`            |
| `image` / `audio` / `stage` manifest   | (no legacy equivalent — filename guessing) |
| `end` block terminators                | indentation-only blocks                    |

## Play-through (headless)

1. Game starts at `label start`.
2. `affection` is `0` (int), `route` is `"none"` (str) — types recorded in `state.declared_types`.
3. `scene bg classroom with fade` → background set; `show eileen happy at center` → actor shown.
4. Eileen's line interpolates: "Hi! Declarative scripts work. Affection is 0."
5. A menu with two choices appears (ids 0 and 1).
6. **Choice 0 "Help Eileen"** → `affection == 1`, `route == "good"` → `jump good` → "Thanks for helping! Route good, affection 1."
7. **Choice 1 "Ignore her"** → `affection == 0`, `route == "neutral"` → `jump neutral` → "Maybe next time. Route neutral."
8. Both routes end with `return` and the game ends cleanly.

## Asset manifest

- `state.assets["images"]["bg classroom"] == "backgrounds/classroom.png"`
- `state.resolve_asset("images", "bg classroom")` returns the path;
  unknown names fall back to the name unchanged.

## Typed state

- `set affection = "text"` raises a runtime `type error` (declared `int`).
- `set route = 3` raises a runtime `type error` (declared `str`).

## Golden trace (choice 0)

`say → menu → assign → assign → jump → say → return → end`

## Verify

```bash
python -m tools.run_headless examples/05_declarative_script/script.rpy --choices 0
python -m tools.run_headless examples/05_declarative_script/script.rpy --choices 1
python -m tools.validate examples/05_declarative_script/script.rpy
pytest tests/test_declarative.py -v
```
