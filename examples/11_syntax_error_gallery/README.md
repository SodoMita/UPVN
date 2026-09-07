# Gallery of syntax errors — M06

Each `.rpy` file here is intentionally broken. `tools/validate.py` and `parser` must fail
with a friendly `file:line:col message` + caret + `Hint:` — no Python traceback.

Run:

```
python -m tools.validate examples/11_syntax_error_gallery/*.rpy   # should FAIL (exit 1) with friendly errors
pytest tests/test_parser_errors.py -v
```

## Cases

- `bad_jump_colon.rpy` — `jump foo:` should hint `does not take a colon`
- `bad_indent.rpy` — 2 spaces indent
- `bad_menu_no_colon.rpy` — `menu` without colon
- `bad_menu_choice_no_colon.rpy` — choice without colon
- `bad_label_no_colon.rpy` — `label start` without colon
- `bad_define_missing_parens.rpy` — `define e = Character`
- `bad_default_call.rpy` — `default foo = some_func()`
- `bad_assign_no_op.rpy` — `$ affection`
- `bad_unknown.rpy` — unknown statement `foo bar`
- `bad_state_type.rpy` — `state:` declares `int` but the value is a string
- `bad_character_no_colon.rpy` — `character e` missing the `:` block marker
- `bad_set_no_op.rpy` — `set affection` missing an operator
- `bad_end_unexpected.rpy` — stray `end` with no open block
- `bad_choice_outside_menu.rpy` — `choice "A":` used outside a `menu:` block
