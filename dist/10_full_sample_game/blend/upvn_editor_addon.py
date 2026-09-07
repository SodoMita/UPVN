"""
UPVN Blender Editor Tools — create visual novel inside Blender with minimal coding
v0.5 polish (2026-09-08): preserve labels, asset browser, side images, arbitrary saves

Install as Blender add-on (UPBGE 0.50 / Blender 5.0+):
    Edit → Preferences → Add-ons → Install → select blend/upvn_editor_addon.py → Enable

Then in 3D Viewport or Text Editor sidebar (N) find tab "UPVN".

Minimal-coding workflow (no .rpy typing):
    1. Create Project → sets //game/script.rpy
    2. Add Character (name, color) → writes `define` to script
    3. Add Scene (bg name) → writes `scene` to script (with optional image picker)
    4. Add Dialogue (speaker, text, [var] supported) → writes `say`
    5. Add Show/Hide (sprite at position with move/dissolve) → writes `show` (with optional sprite image picker)
    6. Add Menu (choices + jumps) → writes `menu`
    7. Validate → runs parser, shows line/col + hint (friendly errors)
    8. Preview → headless screenshot via engine/render/headless_renderer (no UPBGE needed)
    9. Save/Load slots are arbitrary — use any slot number, not 6 slots

The add-on generates clean .rpy (no YAML, no pickle) — direct parser → interpreter pipeline.
Headless fallback: when bpy unavailable (CI), the module still imports and exposes
`UPVN_GameBuilder` Python API used by `tools/upvn_game_creator.py`.
"""

bl_info = {
    "name": "UPVN — Visual Novel Editor",
    "author": "UPVN",
    "version": (0, 5, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > UPVN, Text Editor > Sidebar > UPVN",
    "description": "Create Ren'Py-like visual novel inside Blender with minimal coding — characters, scenes, dialogue, menus, arbitrary saves, preview, asset browser, side images",
    "category": "Game Engine",
}

# ---------------------------------------------------------------- headless-safe imports
try:
    import bpy
    HAS_BPY = True
except ImportError:
    bpy = None
    HAS_BPY = False

import pathlib
import json
import textwrap
import shutil
import re

# core engine imports (work headless)
try:
    from engine.script.parser import parse_string, parse_file
    from engine.core.vn_controller import VNController
    from engine.save.save_manager import SaveManager
    ENGINE_AVAILABLE = True
except ImportError:
    # when running inside Blender, engine may be in different path
    import sys
    import pathlib as _pl
    p = _pl.Path(__file__).parent.parent
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    try:
        from engine.script.parser import parse_string, parse_file
        ENGINE_AVAILABLE = True
    except Exception:
        ENGINE_AVAILABLE = False

# ---------------------------------------------------------------- Python API for minimal coding (works without bpy)

class UPVN_GameBuilder:
    """Headless Python API — also used by Blender operators. Generates .rpy with minimal coding."""

    def __init__(self, script_path: str = "game/script.rpy"):
        self.script_path = pathlib.Path(script_path)
        self.characters = {}  # id -> {name, color}
        self.labels = {"start": []}  # label -> list of lines
        self.current_label = "start"
        self._lines = []  # raw lines for current label
        # ensure project dirs
        self.script_path.parent.mkdir(parents=True, exist_ok=True)
        self._existing_text = None
        # if file exists, load it for preservation
        if self.script_path.exists():
            try:
                self._existing_text = self.script_path.read_text(encoding="utf-8")
                # try parse to populate characters/labels for preview
                if ENGINE_AVAILABLE:
                    try:
                        data = parse_string(self._existing_text, filename=str(self.script_path))
                        for cid, cdata in data.get("characters", {}).items():
                            self.characters[cid] = {"name": cdata["name"], "color": cdata.get("color","#ffffff")}
                        # populate labels structure for internal use (keep existing)
                        self.labels = {}
                        for lbl, nodes in data.get("labels", {}).items():
                            self.labels[lbl] = []  # we keep as empty placeholders; actual lines preserved via _existing_text
                        if "start" not in self.labels:
                            self.labels["start"] = []
                    except:
                        pass
            except:
                pass

    def ensure_label(self, label: str):
        if label not in self.labels:
            self.labels[label] = []
        self.current_label = label
        # if existing text has this label, we will append to it on write
        return self

    def add_character(self, cid: str, name: str, color: str = "#ffffff"):
        self.characters[cid] = {"name": name, "color": color}
        return self

    def add_scene(self, bg: str, transition: str | None = None):
        line = f"    scene {bg}" + (f" with {transition}" if transition else "")
        self.labels[self.current_label].append(line)
        return self

    def add_show(self, asset: str, position: str = "center", transition: str | None = None):
        line = f"    show {asset} at {position}" + (f" with {transition}" if transition else "")
        self.labels[self.current_label].append(line)
        return self

    def add_hide(self, tag: str, transition: str | None = None):
        line = f"    hide {tag}" + (f" with {transition}" if transition else "")
        self.labels[self.current_label].append(line)
        return self

    def add_say(self, who: str | None, text: str):
        esc = text.replace('"', '\\"')
        if who:
            line = f'    {who} "{esc}"'
        else:
            line = f'    "{esc}"'
        self.labels[self.current_label].append(line)
        return self

    def add_menu(self, caption: str | None, choices: list[tuple[str, str]]):
        """choices: list of (text, jump_label)"""
        lines = []
        lines.append("    menu:")
        if caption:
            lines.append(f'        "{caption}"')
        for txt, jump in choices:
            lines.append(f'        "{txt}":')
            lines.append(f'            jump {jump}')
            # ensure jump target exists
            if jump not in self.labels:
                self.labels[jump] = [f'    "{txt} chosen."', "    return"]
        self.labels[self.current_label].extend(lines)
        return self

    def add_jump(self, label: str):
        self.labels[self.current_label].append(f"    jump {label}")
        return self

    def add_camera_zoom(self, zoom: float, duration: float = 1.0, easing: str = "ease"):
        self.labels[self.current_label].append(f"    camera zoom {zoom} duration {duration} with {easing}")
        return self

    def add_stage(self, stage: str):
        self.labels[self.current_label].append(f"    load_stage {stage}")
        return self

    def add_show3d(self, asset: str, marker: str = "center"):
        self.labels[self.current_label].append(f"    show3d {asset} at {marker}")
        return self

    def add_side_image(self, who: str, image: str, side: str = "left"):
        """Side image helper — shows side portrait via show with position alias"""
        # side image convention: show <who> side at <side>
        line = f"    show {who} {image} at {side}"
        self.labels[self.current_label].append(line)
        return self

    def build_rpy(self) -> str:
        out = []
        for cid, data in self.characters.items():
            out.append(f'define {cid} = Character("{data["name"]}", color="{data["color"]}")')
        out.append("")
        for label, lines in self.labels.items():
            out.append(f"label {label}:")
            if not lines:
                out.append('    "Empty label."')
                out.append("    return")
            else:
                out.extend(lines)
                # ensure return if no jump/return at end
                last = lines[-1].strip()
                if not last.startswith("jump ") and last != "return" and "menu:" not in "\n".join(lines[-3:]):
                    pass
            out.append("")
        return "\n".join(out)

    def write(self):
        # Preserve mode: if _existing_text exists, merge new additions rather than overwrite cleanly?
        # New logic: if file existed and we have _existing_text, we merge by appending new label lines
        # and inserting new defines at top after last define.
        if self._existing_text is not None and self.script_path.exists():
            existing = self.script_path.read_text(encoding="utf-8")
            # collect new defines that are not already in existing
            new_defines = []
            for cid, data in self.characters.items():
                define_line = f'define {cid} = Character("{data["name"]}", color="{data["color"]}")'
                if define_line not in existing and f'define {cid} =' not in existing:
                    new_defines.append(define_line)
            # collect new label lines (those in self.labels[current] that are not in existing)
            # Simpler: just append new lines for current_label to the end of that label's block in existing file
            # Find label block for current_label and insert before next label or end
            if self.current_label in existing:
                # find label occurrence
                lines = existing.splitlines()
                # locate label line
                label_idx = None
                for i, l in enumerate(lines):
                    if re.match(rf'^\s*label\s+{re.escape(self.current_label)}\s*:', l):
                        label_idx = i
                        break
                if label_idx is not None:
                    # find next label after
                    next_idx = None
                    for j in range(label_idx+1, len(lines)):
                        if re.match(r'^\s*label\s+\w+\s*:', lines[j]):
                            next_idx = j
                            break
                    # insert new lines before next_idx or at end
                    insert_at = next_idx if next_idx is not None else len(lines)
                    # new lines to insert are those in self.labels[current_label] that are not already in block
                    block = lines[label_idx+1:insert_at] if insert_at else []
                    block_text = "\n".join(block)
                    to_insert = []
                    for nl in self.labels[self.current_label]:
                        if nl.strip() not in block_text:
                            to_insert.append(nl)
                    if to_insert:
                        # insert
                        new_lines = lines[:insert_at] + to_insert + lines[insert_at:]
                        # insert new defines at top after last define or after imports
                        if new_defines:
                            last_define_idx = -1
                            for k, l in enumerate(new_lines):
                                if l.strip().startswith("define "):
                                    last_define_idx = k
                            if last_define_idx >= 0:
                                for nd in reversed(new_defines):
                                    new_lines.insert(last_define_idx+1, nd)
                            else:
                                # insert at top
                                new_lines = new_defines + [""] + new_lines
                        self.script_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                        return self.script_path
            # fallback: if we couldn't merge cleanly, append new defines at top and new lines at end
            if new_defines:
                existing = "\n".join(new_defines) + "\n" + existing
            # append new label blocks that don't exist yet
            new_rpy = self.build_rpy()
            # For simplicity, if current_label lines were not merged, append them
            # Check if any new lines not in existing, append at end of current label block via simple append
            # We'll just write merged via appending to_insert if exists else fallback to overwrite prevention: append at end
            # Last resort: overwrite with build_rpy but preserve original defines+labels that were not in builder
            # To avoid data loss, we append to existing file directly for new lines
            if to_insert if 'to_insert' in locals() else []:
                # already handled
                pass
            else:
                # no merge, just append new lines for current label at end of file
                extra = "\n".join(self.labels[self.current_label])
                if extra.strip() and extra.strip() not in existing:
                    # append inside current label: find label and append before next label
                    # simple: append at end of file
                    self.script_path.write_text(existing.rstrip() + "\n" + extra + "\n", encoding="utf-8")
                    return self.script_path
            # if still not written, fall through to full write
        rpy = self.build_rpy()
        self.script_path.write_text(rpy, encoding="utf-8")
        return self.script_path

    def validate(self):
        if not ENGINE_AVAILABLE:
            return True, "engine not available — skip validate"
        # if we have existing file, validate that file, not just built
        if self.script_path.exists():
            try:
                parse_file(str(self.script_path))
                return True, "OK (file)"
            except Exception as e:
                return False, str(e)
        rpy = self.build_rpy()
        try:
            parse_string(rpy)
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def preview_screenshot(self, out_path: str = "screenshots/upvn_preview.png"):
        """Headless screenshot via headless_renderer."""
        if not ENGINE_AVAILABLE:
            return None
        from engine.render.headless_renderer import render_state
        from engine.core.vn_state import VNState
        from engine.core.vn_interpreter import VNInterpreter
        # prefer file on disk if exists
        if self.script_path.exists():
            try:
                script = parse_file(str(self.script_path))
            except Exception:
                rpy = self.build_rpy()
                script = parse_string(rpy)
        else:
            rpy = self.build_rpy()
            try:
                script = parse_string(rpy)
            except Exception as e:
                return None
        state = VNState()
        interp = VNInterpreter(script, state)
        gen = interp.run()
        try:
            ev = next(gen)
            while not ev.get("wait"):
                ev = next(gen)
        except StopIteration:
            ev = {"type": "say", "who": None, "text": "Preview"}
        img = render_state(state, ev, pathlib.Path(out_path))
        return pathlib.Path(out_path)

# ---------------------------------------------------------------- Blender operators (only if HAS_BPY)

if HAS_BPY:
    # properties
    class UPVN_SceneProps(bpy.types.PropertyGroup):
        project_path: bpy.props.StringProperty(name="Script Path", default="//game/script.rpy", subtype='FILE_PATH')
        char_id: bpy.props.StringProperty(name="ID", default="e")
        char_name: bpy.props.StringProperty(name="Name", default="Eileen")
        char_color: bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', size=4, default=(0.78, 1.0, 0.78, 1.0), min=0, max=1)
        bg_name: bpy.props.StringProperty(name="Background", default="bg classroom")
        bg_image: bpy.props.StringProperty(name="BG Image (optional)", default="", subtype='FILE_PATH')
        speaker: bpy.props.StringProperty(name="Speaker (empty=narration)", default="e")
        dialogue: bpy.props.StringProperty(name="Text", default="Hello from Blender!")
        show_asset: bpy.props.StringProperty(name="Asset", default="eileen")
        show_pos: bpy.props.EnumProperty(name="Position", items=[("left","Left",""),("center","Center",""),("right","Right",""),("far_left","Far Left",""),("far_right","Far Right","")], default="center")
        show_trans: bpy.props.StringProperty(name="With (move/dissolve/fade)", default="move")
        sprite_image: bpy.props.StringProperty(name="Sprite Image (optional)", default="", subtype='FILE_PATH')
        side_image: bpy.props.StringProperty(name="Side Image Tag", default="")
        menu_caption: bpy.props.StringProperty(name="Menu Caption", default="What do you do?")
        menu_choice1: bpy.props.StringProperty(name="Choice 1", default="Ask her")
        menu_jump1: bpy.props.StringProperty(name="Jump 1", default="ask")
        menu_choice2: bpy.props.StringProperty(name="Choice 2", default="Wait")
        menu_jump2: bpy.props.StringProperty(name="Jump 2", default="wait")
        stage_name: bpy.props.StringProperty(name="3D Stage", default="classroom_3d")
        arbitrary_slot: bpy.props.IntProperty(name="Arbitrary Slot", default=1, min=1, max=999999, description="Any slot 1..∞ (pagination 6/page)")

    class UPVN_OT_CreateProject(bpy.types.Operator):
        bl_idname = "upvn.create_project"
        bl_label = "Create UPVN Project"
        bl_description = "Create //game/script.rpy with starter template (no coding)"
        def execute(self, context):
            props = context.scene.upvn_props
            path = bpy.path.abspath(props.project_path)
            builder = UPVN_GameBuilder(path)
            builder.add_character("e", "Eileen", "#c8ffc8")
            builder.add_character("s", "Sylvie", "#c8c8ff")
            builder.ensure_label("start")
            builder.add_scene("bg classroom")
            builder.add_show("eileen", "center")
            builder.add_say("e", "Hello from Blender! This game was created with clicks, not code.")
            builder.add_say(None, "You can add more dialogue, menus, and 3D stages from the UPVN panel.")
            builder.write()
            self.report({'INFO'}, f"Created {path}")
            return {'FINISHED'}

    class UPVN_OT_AddCharacter(bpy.types.Operator):
        bl_idname = "upvn.add_character"
        bl_label = "Add Character"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            col = p.char_color
            hexcol = "#{:02x}{:02x}{:02x}".format(int(col[0]*255), int(col[1]*255), int(col[2]*255))
            builder.add_character(p.char_id, p.char_name, hexcol)
            builder.write()
            self.report({'INFO'}, f"Added character {p.char_id}={p.char_name} (preserved labels)")
            return {'FINISHED'}

    class UPVN_OT_AddScene(bpy.types.Operator):
        bl_idname = "upvn.add_scene"
        bl_label = "Add Scene"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            # asset browser: if bg_image picked, copy to assets and use basename
            bg = p.bg_name
            if p.bg_image:
                try:
                    src = pathlib.Path(bpy.path.abspath(p.bg_image))
                    if src.exists():
                        dest_dir = pathlib.Path(path).parent.parent / "assets" / "backgrounds"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest = dest_dir / src.name
                        shutil.copy2(src, dest)
                        bg = f"bg {src.stem}"
                        self.report({'INFO'}, f"Copied BG {src.name} → {dest}")
                except Exception as e:
                    self.report({'WARNING'}, f"BG copy failed {e}")
            builder.add_scene(bg)
            builder.write()
            self.report({'INFO'}, f"Added scene {bg} (with asset browser)")
            return {'FINISHED'}

    class UPVN_OT_AddDialogue(bpy.types.Operator):
        bl_idname = "upvn.add_dialogue"
        bl_label = "Add Dialogue"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            who = p.speaker.strip() or None
            builder.add_say(who, p.dialogue)
            builder.write()
            self.report({'INFO'}, f"Added say {who or 'Narration'}: {p.dialogue[:30]}")
            return {'FINISHED'}

    class UPVN_OT_AddShow(bpy.types.Operator):
        bl_idname = "upvn.add_show"
        bl_label = "Add Show"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            trans = p.show_trans.strip() or None
            asset = p.show_asset
            if p.sprite_image:
                try:
                    src = pathlib.Path(bpy.path.abspath(p.sprite_image))
                    if src.exists():
                        dest_dir = pathlib.Path(path).parent.parent / "assets" / "sprites"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest = dest_dir / src.name
                        shutil.copy2(src, dest)
                        asset = src.stem
                        self.report({'INFO'}, f"Copied sprite {src.name} → {dest}")
                except Exception as e:
                    self.report({'WARNING'}, f"Sprite copy failed {e}")
            builder.add_show(asset, p.show_pos, trans)
            # side image support
            if p.side_image.strip():
                builder.add_side_image(asset, p.side_image.strip(), p.show_pos)
            builder.write()
            self.report({'INFO'}, f"Added show {asset} at {p.show_pos} with {trans}")
            return {'FINISHED'}

    class UPVN_OT_AddMenu(bpy.types.Operator):
        bl_idname = "upvn.add_menu"
        bl_label = "Add Menu"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            builder.add_menu(p.menu_caption, [(p.menu_choice1, p.menu_jump1), (p.menu_choice2, p.menu_jump2)])
            builder.write()
            self.report({'INFO'}, f"Added menu {p.menu_caption} (preserved)")
            return {'FINISHED'}

    class UPVN_OT_AddStage(bpy.types.Operator):
        bl_idname = "upvn.add_stage"
        bl_label = "Add 3D Stage"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            builder.add_stage(p.stage_name)
            builder.add_show3d("eileen", "marker_eileen")
            builder.write()
            self.report({'INFO'}, f"Added 3D stage {p.stage_name} + show3d")
            return {'FINISHED'}

    class UPVN_OT_Validate(bpy.types.Operator):
        bl_idname = "upvn.validate"
        bl_label = "Validate Script"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            text = pathlib.Path(path).read_text(encoding="utf-8") if pathlib.Path(path).exists() else ""
            if not ENGINE_AVAILABLE:
                self.report({'WARNING'}, "Engine not available")
                return {'FINISHED'}
            try:
                parse_string(text, filename=path)
                self.report({'INFO'}, "Validate OK — no errors")
            except Exception as e:
                self.report({'ERROR'}, str(e).splitlines()[0][:120])
            return {'FINISHED'}

    class UPVN_OT_Preview(bpy.types.Operator):
        bl_idname = "upvn.preview"
        bl_label = "Preview Screenshot"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            out = builder.preview_screenshot()
            if out and out.exists():
                self.report({'INFO'}, f"Preview at {out} ({out.stat().st_size//1024}KB)")
                try:
                    img = bpy.data.images.load(str(out), check_existing=True)
                    for area in bpy.context.screen.areas:
                        if area.type == 'IMAGE_EDITOR':
                            area.spaces.active.image = img
                except: pass
            else:
                self.report({'ERROR'}, "Preview failed")
            return {'FINISHED'}

    class UPVN_OT_SaveSlotDemo(bpy.types.Operator):
        bl_idname = "upvn.save_demo"
        bl_label = "Save Demo (arbitrary slot)"
        bl_description = "Demo arbitrary save slots: saves to next available slot or chosen slot"
        def execute(self, context):
            p = context.scene.upvn_props
            from engine.core.vn_state import VNState
            from engine.save.save_manager import SaveManager
            state = VNState()
            state.variables["demo"] = 1
            sm = SaveManager(state)
            slot = int(p.arbitrary_slot) if p.arbitrary_slot else sm.next_available_slot()
            # if slot exists, next available to avoid overwrite? Use chosen
            sm.save(slot)
            self.report({'INFO'}, f"Saved to arbitrary slot {slot} (1..∞)")
            ids = sm.list_slot_ids()
            self.report({'INFO'}, f"Slots now: {ids} — pagination 6/page, page {(slot-1)//6+1}")
            return {'FINISHED'}

    class UPVN_OT_QuickPreviewArbitrary(bpy.types.Operator):
        bl_idname = "upvn.preview_arbitrary"
        bl_label = "Preview Arbitrary Saves"
        def execute(self, context):
            p = context.scene.upvn_props
            # generate a preview screenshot of save overlay pagination
            try:
                from engine.render.headless_renderer import render_state
                from engine.core.vn_state import VNState
                from engine.save.save_manager import SaveManager
                from engine.ui.screen_manager import ScreenManager
                import tempfile
                state = VNState()
                state.history.append({"who": None, "who_name": "Narrator", "text": "Arbitrary save demo", "stripped": "Arbitrary save demo"})
                sm = SaveManager(state, save_dir=str(pathlib.Path(bpy.path.abspath(p.project_path)).parent / "saves"))
                # create dummy saves up to chosen slot for pagination demo
                for i in [1,2,7,42,100,500]:
                    try:
                        state.variables["slot_test"] = i
                        sm.save(i)
                    except: pass
                mgr = ScreenManager(state, sm)
                from engine.ui.screen_manager import SaveScreen
                save_screen = SaveScreen(sm)
                save_screen.page = (int(p.arbitrary_slot)-1)//6
                mgr.show("save", save_screen)
                from pathlib import Path
                out = Path("screenshots/upvn_arbitrary_preview.png")
                render_state(state, {"type": "say", "who": None, "text": "Arbitrary preview"}, out, screen_mgr=mgr)
                self.report({'INFO'}, f"Arbitrary preview at {out} page {save_screen.page+1}")
            except Exception as e:
                self.report({'ERROR'}, f"Arbitrary preview failed {e}")
            return {'FINISHED'}

    def _builder_from_file(path: str) -> UPVN_GameBuilder:
        """Load existing script.rpy into builder preserving labels (v0.5 fix)."""
        # Use UPVN_GameBuilder's own preservation logic (it loads _existing_text)
        b = UPVN_GameBuilder(path)
        # ensure current label is last label in file if exists, so new ops append to correct place
        # Try to detect last label in file
        try:
            p = pathlib.Path(path)
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                # find last label
                m = list(re.finditer(r'^\s*label\s+(\w+)\s*:', txt, flags=re.M))
                if m:
                    last_label = m[-1].group(1)
                    b.ensure_label(last_label)
                # also try to load characters already parsed (b already did)
        except:
            pass
        return b

    class UPVN_PT_MainPanel(bpy.types.Panel):
        bl_label = "UPVN — Visual Novel"
        bl_idname = "UPVN_PT_main"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "UPVN"
        def draw(self, context):
            layout = self.layout
            props = context.scene.upvn_props
            layout.label(text="Project", icon='FILE_FOLDER')
            layout.prop(props, "project_path")
            layout.operator("upvn.create_project", icon='ADD')
            layout.separator()
            layout.label(text="Characters (no coding)", icon='USER')
            layout.prop(props, "char_id")
            layout.prop(props, "char_name")
            layout.prop(props, "char_color")
            layout.operator("upvn.add_character", icon='ADD')
            layout.separator()
            layout.label(text="Scene & Sprites (asset browser)", icon='IMAGE_DATA')
            layout.prop(props, "bg_name")
            layout.prop(props, "bg_image")
            layout.operator("upvn.add_scene", icon='SCENE_DATA')
            layout.prop(props, "show_asset")
            layout.prop(props, "show_pos")
            layout.prop(props, "show_trans")
            layout.prop(props, "sprite_image")
            layout.prop(props, "side_image")
            layout.operator("upvn.add_show", icon='OBJECT_DATA')
            layout.operator("upvn.add_stage", icon='MESH_CUBE')
            layout.prop(props, "stage_name")
            layout.separator()
            layout.label(text="Dialogue", icon='SPEAKER')
            layout.prop(props, "speaker")
            layout.prop(props, "dialogue")
            layout.operator("upvn.add_dialogue", icon='ADD')
            layout.separator()
            layout.label(text="Menu (branching)", icon='QUESTION')
            layout.prop(props, "menu_caption")
            layout.prop(props, "menu_choice1")
            layout.prop(props, "menu_jump1")
            layout.prop(props, "menu_choice2")
            layout.prop(props, "menu_jump2")
            layout.operator("upvn.add_menu", icon='ADD')
            layout.separator()
            layout.label(text="Tools", icon='TOOL_SETTINGS')
            row = layout.row(align=True)
            row.operator("upvn.validate", icon='CHECKMARK')
            row.operator("upvn.preview", icon='RENDER_RESULT')
            layout.operator("upvn.save_demo", icon='FILE_TICK')
            layout.prop(props, "arbitrary_slot")
            layout.operator("upvn.preview_arbitrary", icon='IMAGE_REFERENCE')
            layout.label(text="Saves: arbitrary slots 1..∞ (←→ pagination)", icon='INFO')
            layout.label(text="H: history  Q: quick menu  Preserved labels", icon='INFO')

    class UPVN_PT_TextPanel(bpy.types.Panel):
        bl_label = "UPVN — Script"
        bl_idname = "UPVN_PT_text"
        bl_space_type = 'TEXT_EDITOR'
        bl_region_type = 'UI'
        bl_category = "UPVN"
        def draw(self, context):
            layout = self.layout
            layout.label(text="Edit script.rpy inside Blender")
            layout.operator("upvn.validate", icon='CHECKMARK')
            layout.operator("upvn.preview", icon='RENDER_RESULT')

    classes = (UPVN_SceneProps, UPVN_OT_CreateProject, UPVN_OT_AddCharacter, UPVN_OT_AddScene,
               UPVN_OT_AddDialogue, UPVN_OT_AddShow, UPVN_OT_AddMenu, UPVN_OT_AddStage, UPVN_OT_Validate,
               UPVN_OT_Preview, UPVN_OT_SaveSlotDemo, UPVN_OT_QuickPreviewArbitrary, UPVN_PT_MainPanel, UPVN_PT_TextPanel)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.Scene.upvn_props = bpy.props.PointerProperty(type=UPVN_SceneProps)
        print("[UPVN] Editor addon v0.5 registered — View3D > Sidebar > UPVN (preserve+asset browser+arbitrary)")

    def unregister():
        for cls in reversed(classes):
            try:
                bpy.utils.unregister_class(cls)
            except: pass
        del bpy.types.Scene.upvn_props
        print("[UPVN] Editor addon unregistered")

    if __name__ == "__main__":
        register()

# expose builder for headless tests
__all__ = ["UPVN_GameBuilder"]
