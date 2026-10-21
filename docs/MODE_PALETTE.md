# Mode Palette (v1.17.0)

When you select an Arraytron node, its **Parameters pane** starts with a row of **big icon cells, one per Distribution Mode, the title under each icon**: Line, Area, Grid, Circle, Curve, Surface, Paint, Cluster, Imported, Place and Biome. The selected mode is **lit** (a warm tile with a yellow frame), the others are **dim**; hover a cell for a highlight; **click a cell to choose that mode**. Below the row are the node's own parameters (tabs, folders, the Distribution Mode dropdown), exactly as before.

It looks and works like the brush row of Houdini's Paint Instances node, for the same reason: it is a **Python Panel registered for the Arraytron node type** (`showInParametersPane`), so Houdini shows it in the Parameters pane instead of the plain dialog. The panel puts the palette on top and embeds the real parameter dialog (`hou.qt.ParmDialog`) below it, so nothing about the parameters changes: not one parameter was added, removed or moved, the mode menu is the same, and every file written by the node is identical to v1.16.0. A change of the mode anywhere (the dropdown, a script, an undo) shows on the palette within a quarter of a second.

## Where it lives

* The widget code is `src/arraytron_modepanel.py`: the palette (`ModePalette`, plain PySide: PySide6 in Houdini 21 and 22, PySide2 in 20.5) and the pane (`ParmPanel`), with the pane hooks Houdini calls (`onCreateInterface`, `onNodePathChanged`, ...). The builder embeds it in the HDA as the section `ModePalette.py` with the icons filled in.
* The installer is `install_parm_panel` in `src/arraytron_modepalette.py` (part of the PythonModule). The `OnCreated` and `OnLoaded` scripts of the HDA call it: it writes a `.pypanel` to the temp folder with this node type in `<showInParametersPane optype=...>` and installs it into the session. Nothing has to be installed on disk; the installer package is unchanged.
* The icons are drawn by code: `tools/make_mode_icons.py` writes 22 SVGs to `icon/modes/` (`Mode_<key>_on.svg` and `_off.svg`: a dark tile with a dim glyph, a warm lit tile with a glow and a bright glyph). The Paint icon is a simple outline brush. Change a colour or a glyph in that script and rebuild.

## If it does not suit you

Set the environment variable **`ARRAYTRON_NO_PARM_PANEL=1`** before starting Houdini and the node shows Houdini's plain parameter dialog again (the dropdown always stays in it). With no interface (hython, a render farm) the installer does nothing.

## Evidence and limits

`tests/validate_modepanel.py` (4 groups, 4 mutations) proves what does not need the interface: the HDA carries the panel code and all 22 icons; every icon is valid SVG; every mode of the menu has a title and a lit and a dim icon; the installer builds a valid `.pypanel` for this node type with `showInParametersPane`, installs it once, honours the kill switch and does nothing without an interface; the hooks call it and the node is still renamed `arraytron1`; the parameters, the mode menu and the output are those of the previous release.

**Verified in the GUI by a run in Houdini 20.5 (with an interface, screenshots):** the row of 11 cells with the titles under them inside the Parameters pane of the Biome demo, the lit cell, a click on Surface switching the dropdown and the Layout tab, the Paint brush icon. **Not yet verified:** Houdini 21 and 22 with this build (the code is the same; Houdini 22 was checked with the first version of the palette as a floating window), a very narrow Parameters pane (the cells wrap to rows of six), and how it feels with several Arraytron nodes selected.
