"""M26g regression: GUI-scope NameErrors in the editor add-on.

Field bug (found live in the UPBGE 0.50 GUI, 2026-09-11): ``_rewrite_unlit``
referenced ``TEX_NODE_NAME`` / ``MIX_NODE_NAME`` and ``_ensure_white_image``
referenced ``WHITE_IMAGE_NAME`` — but those names were only bound as LOCALS
inside ``build_vn_scene``. Every ``tex_capable=True`` material (all sprite
planes) crashed with ``NameError`` the first time *Setup Scene* ran in the
real editor GUI. Headless tests never saw it: the helpers live under
``if HAS_BPY:`` and pytest runs without bpy.

These tests statically verify, with ``symtable``, that every free name the
material helpers use is resolvable at module scope of the add-on source —
no bpy needed, catches the whole bug class (helper-under-``if HAS_BPY``
referencing another function's locals).
"""

import pathlib
import symtable

import pytest

ADDON = pathlib.Path(__file__).resolve().parent.parent / "blend" / "upvn_editor_addon.py"


def _module_table():
    return symtable.symtable(ADDON.read_text(encoding="utf-8"), str(ADDON), "exec")


def _find(table, name):
    for child in table.get_children():
        if child.get_name() == name:
            return child
        found = _find(child, name)
        if found is not None:
            return found
    return None


def _module_globals(table):
    # all names bound at module scope (imports, assignments, defs, classes)
    return {s.get_name() for s in table.get_symbols()}


@pytest.mark.parametrize("helper", ["_rewrite_unlit", "_ensure_white_image"])
def test_material_helpers_only_reference_module_or_local_names(helper):
    import builtins
    table = _module_table()
    fn = _find(table, helper)
    assert fn is not None, f"{helper} not found in add-on source"
    # free names used by the helper = its globals once it is defined
    used = {s.get_name() for s in fn.get_symbols()
            if s.is_global() and not s.is_assigned()}
    missing = used - _module_globals(table) - set(dir(builtins))
    assert not missing, (
        f"{helper} references {sorted(missing)} which are neither local nor "
        f"module-level — they are probably locals of another function "
        f"(GUI NameError, M26g bug class)"
    )


def test_contract_names_are_module_level():
    """TEX_NODE_NAME / MIX_NODE_NAME / WHITE_IMAGE_NAME must be module
    globals so the if-HAS_BPY helpers can see them."""
    table = _module_table()
    g = _module_globals(table)
    for name in ("TEX_NODE_NAME", "MIX_NODE_NAME", "WHITE_IMAGE_NAME"):
        assert name in g, f"{name} must be bound at module scope of the add-on"


def test_fallback_constants_match_engine_contract():
    """The hardcoded fallbacks in the add-on must mirror the engine contract
    (they are used whenever the engine import fails, e.g. before discovery)."""
    import sys
    root = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    try:
        from engine.render import contract as C
    finally:
        sys.path.remove(str(root))
    src = ADDON.read_text(encoding="utf-8")
    assert f'TEX_NODE_NAME, MIX_NODE_NAME = "{C.TEX_NODE_NAME}", "{C.MIX_NODE_NAME}"' in src
    assert f'WHITE_IMAGE_NAME = "{C.WHITE_IMAGE_NAME}"' in src


def test_build_vn_scene_does_not_shadow_contract_names():
    """build_vn_scene must not rebind the three shared names as locals —
    that is exactly the M26g regression shape (shadows don't reach the
    module helpers, and a reader can't tell which binding wins)."""
    table = _module_table()
    fn = _find(table, "build_vn_scene")
    assert fn is not None
    local = {s.get_name() for s in fn.get_symbols() if s.is_local()}
    for name in ("TEX_NODE_NAME", "MIX_NODE_NAME", "WHITE_IMAGE_NAME"):
        assert name not in local, (
            f"build_vn_scene binds {name} locally — hoist it to module scope "
            f"instead (the material helpers read the module global)"
        )


def _bpy_classes_and_registration():
    """AST-walk the add-on: classes whose base is a bpy.types.X and the
    contents of the `classes = (...)` registration tuple."""
    import ast
    tree = ast.parse(ADDON.read_text(encoding="utf-8"))
    defined, registered = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                # accept both `bpy.types.Panel` (nested attribute) and a
                # hypothetical bare `bpy.Panel`
                if not (isinstance(base, ast.Attribute)
                        and base.attr in ("Panel", "Operator", "PropertyGroup",
                                          "AddonPreferences", "Menu", "UIList")):
                    continue
                v = base.value
                is_bpy = (isinstance(v, ast.Name) and v.id == "bpy") or (
                    isinstance(v, ast.Attribute) and v.attr == "types"
                    and isinstance(v.value, ast.Name) and v.value.id == "bpy")
                if is_bpy:
                    defined.add(node.name)
        if (isinstance(node, ast.Assign)
                and any(t.id == "classes" for t in node.targets if isinstance(t, ast.Name))):
            registered = {e.id for e in node.value.elts if isinstance(e, ast.Name)}
    return defined, registered


def test_every_bpy_class_is_registered():
    """M26g bug: UPVN_Prefs (AddonPreferences) was defined but missing from
    the classes tuple — its Preferences page never appeared and 'Locate
    Engine' could not persist its choice."""
    defined, registered = _bpy_classes_and_registration()
    missing = defined - registered
    assert not missing, f"bpy classes defined but never registered: {sorted(missing)}"
    # and nothing registered that doesn't exist
    assert not (registered - defined), f"classes tuple references undefined: {sorted(registered - defined)}"
