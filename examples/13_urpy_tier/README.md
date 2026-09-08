# `.urpy` tier (fully declarative)

`.urpy` is UPVN's strict, declarative visual-novel language. It contains **zero**
embedded Python — no `$`, no `define`, no `default`, no `python:`/`init` blocks.

## Rules

- State is declared in a typed `state:` block (`affection: int = 0`).
- Characters live in `character id:` blocks (`name`, `color`).
- Assets are declared explicitly: `image` / `audio` / `stage`.
- Assignment is `set`, menu items are `choice "Text":`.
- **Every block must be closed with an explicit `end`** (label / state / character /
  menu / choice / if-chain).

## Run it

```bash
python tools/run_headless.py examples/13_urpy_tier/script.urpy --choices 0
python tools/validate.py examples/13_urpy_tier/script.urpy
```

`.urpy` files parse to the same IR as `.rpy`, so the engine and interpreter treat all
three tiers identically.
