# Arraytron changelog

Newest first. Versions are plain `vMAJOR.MINOR.PATCH`; every release is its own node type `arraytron::instancer::<version>`. Each release reproduces the previous one exactly with its new features off (tested). Details: `docs/VERSIONING.md`, `STATUS.md`, `docs/DECISIONS.md`.

## v1.18.0 - Asset Library
* **Asset Library** (Parameters pane, under the Mode Palette): a local catalogue of USD assets with **your own categories** (Trees, Plants, Rocks, Props by default). Import from the **Solaris Asset Catalog** (names, thumbnails, tags), from USD files, from a folder or by dragging files; search by name or tag; **Add to Bank** (or double-click) puts an asset into the Prototype Bank as a USD File row. Thumbnails for plain USD files are drawn by a small software renderer. One JSON file per user (`Documents/Arraytron/library`, or `ARRAYTRON_LIBRARY`). Logic in the HDA's PythonModule (usable from scripts), Qt section in the panel. Documentation `docs/ASSET_LIBRARY.md`.
* **Stagger Rows is a slider** (0 to 1, the fraction of the gap; 0 off, 0.5 the old brick pattern) instead of a tick. Earlier releases are unchanged.
* New suite `tests/validate_library.py` (6 groups, 4 mutations); the Rows suite checks the slider. Both builds.

## v1.17.0 - Mode Palette
* **The Distribution Mode is chosen on a palette of big icon cells** at the top of the node's Parameters pane: one cell per mode with its **title under the icon**, the selected one lit (warm tile, yellow frame), the others dim; click a cell to choose the mode. It is a Python Panel registered for the Arraytron node type (like the brush row of Paint Instances) with the node's own parameter dialog embedded below it: no parameter was added, removed or moved and the output is identical to v1.16.0. Icons are drawn by code (`tools/make_mode_icons.py`, 22 SVGs embedded in the HDA); the Paint icon is a simple brush. `ARRAYTRON_NO_PARM_PANEL=1` keeps Houdini's plain dialog.
* New suite `tests/validate_modepanel.py` (4 groups, 4 mutations). Both builds (PySide6 / PySide2). Documentation `docs/MODE_PALETTE.md`.

## v1.16.0 - Biome effect
* **Effect per condition** in every Biome row (Layout tab, Biomes table): *Elevation / Slope / Moisture / Temperature Effect* (0 to 1, default 1). 1 is the condition as set, 0 ignores it completely, in between it only partly counts (`weight = 1 - effect * (1 - band)`), so a biome can follow the elevation but not the temperature. Defaults reproduce v1.15.0 exactly.
* `tests/validate_biome.py` now has 8 groups and 7 mutations (`biome_effect`). The demo uses the Effect on the Shore stones. Both builds. Documentation `docs/BIOME.md`.

## v1.15.0 - Biome
* **New Distribution Mode: Biome** (Layout tab): rule based scatter on a terrain. A table of biomes; every row has its conditions (**elevation, slope, moisture, temperature**, each a range with a soft edge), a density, a **Prototype Mix** (bank rows with weights) and a scale range. Biomes blend at their borders (an ecotone): a candidate survives with the probability of the product of its four band weights, with the id keyed hash of the Mask, so a higher density only ever adds points and biomes never move each other's points.
* **Fields:** elevation, slope (face or smooth normals), moisture (constant, noise, distance to a water mesh or curve, an image; with variation and bias) and temperature (base minus a lapse rate, noise, a warm facing). **Primvar: biome**, a **Biome** colour for the debug view, a per-biome read-out.
* New suite `tests/validate_biome.py` (7 groups, 6 mutations) and a demo (forest, alpine firs, cliff rocks, shore stones on a hilly terrain with a pond). Both builds. Documentation `docs/BIOME.md`.

## v1.14.0 - Rows
* **Rows** (Layout tab, section ROWS; Line, Circle / Radial and Curve): the path is laid out in several parallel rows (next to each other, concentric rings, copies of the curve pushed to the side) with *Row Spacing*, *Centre The Rows*, *Random Offset* (across), *Random Shift Along*, *Stagger Rows* and a seed. The count of the mode is the points of one row. Row 0 keeps its ids; the other rows get derived ids, so changing the number of rows never renames a point. It runs right after the distribution, so the Mask, Field Stack, Falloff, Variation and everything after it work on every row. Off by default: the output is exactly v1.13.0.
* The Curve generator writes the direction of the path (`pathdir`) on its points. New suite `tests/validate_rows.py` (6 groups, 6 mutations) and a demo. Both builds. Documentation `docs/ROWS.md`.

## v1.13.0 - Falloff follows the mode, renamed tabs, Export tab
* **Falloff respects the other modes** (*Region: Automatic*): **Cluster** fades every cluster to its own boundary (centre and radius of each cluster, not the box or circle around all of them); **Paint** fades across the width of every stroke (the viewport brush now records the path of each Add / Replace stroke, stored in the Paint Data as `p2`; scenes painted earlier fall back to the whole layout); **Grid** uses all three axes when it has layers in Y (a 3D matrix), so its top and bottom boundaries count too. *Whole layout* keeps the v1.12.0 behaviour.
* **Tabs renamed:** Source -> **Prototypes**, Look -> **Variation**, Finish -> **Debugging**; **Export USD** and the cache read-out moved to a new **Export** tab (nine tabs). Parameter names did not change.
* New suite groups: falloff 10 groups / 10 mutations, paint 18 groups / 5 more mutations (stroke paths). Both builds. Documentation `docs/FALLOFF.md`.

## v1.12.0 - Falloff
* **Falloff** (Layout tab, section FALLOFF): the scatter is full size and densest in the centre and fades towards the edges, in scale and in density. Works with every Distribution Mode; Radial or Box shape (every edge of a rectangle fades), Linear / Smooth / Gaussian curve, a flat centre, an edge density and an edge scale, automatic or custom centre and reach, X and Z or X, Y and Z. After the Mask and the Field Stack (their results are kept), before the Variation. Off by default: the output is exactly v1.11.0.
* New suite `tests/validate_falloff.py` (6 groups, 6 mutations) and a demo (plain, radial and box patches). Both builds. Documentation `docs/FALLOFF.md`.

## v1.11.0 - Place tool extras and cleanups
* **Place tool:** press, drag, release (drag sideways to turn, up or down to scale the new instance; a heading line in the marker); **Snap Position** (grid, kept on the surface) and **Snap Rotation (deg)**; **Place Along Curve** (a BasisCurves prim, by count or spacing, following the curve, optionally projected on the surface).
* **Cleanups:** a new Arraytron node is called `arraytron1` (not `instancer1`); the Physics Settle switch is called **Settle Instances**.
* `tests/validate_place.py` now has 14 groups and 13 mutations; the Place demo gets stepping stones along a curve. Both builds.

## v1.10.0 - Instance Place arrays
* **Copies:** any row of the Placed Instances table can make an array like the Copy and Transform SOP: *Copies*, *Step Translate*, *Step Rotate*, *Step Scale* and *Step Space* (Local follows the copy: spirals, fans, squares; World: straight rows). Copy 0 keeps the row id, the other copies get stable ids derived from it (`1000000000 + id * 10000 + k`); a row without copies is exactly as before.
* The viewport tool places arrays too: new settings *New Copies*, *New Step Translate / Rotate / Scale / Space*; Ctrl+click on a copy deletes its whole row.
* `tests/validate_place.py` now has 11 groups and 9 mutations (arrays against 4x4 matrix products); the Place demo shows a spiral and a fence. Both builds.

## v1.9.0 - Instance Place
* **New Distribution Mode: Instance Place** (Layout tab): instances are placed one at a time, like the transforms of a Copy and Transform SOP. A table (*Placed Instances*) holds every instance: on, stable id, position, rotation, scale and the Prototype Bank row it uses. Mask, Field Stack, Separation, Physics, Instance Overrides, Grow, Variation and primvars work on placed instances like on any others.
* **Place Instances in Viewport:** click a surface to add one instance (aligned to the surface normal if you want, with the New Scale, New Rotation and New Prototype Row settings); Ctrl+click deletes the one under the mouse; wheel and keys change the settings; every click is one undo step. Selecting the node never starts the tool. Fix Ids writes unique ids into rows that have none.
* New suite `tests/validate_place.py` (8 groups, 5 mutations); demo `Arraytron_v1.9.0_place_demo.hip`; documentation `docs/INSTANCE_PLACE.md`. Both builds. New VEX folder `src/vex_v190` (a placed instance may name its Prototype Bank row).

## v1.8.0 - LOD generator
* **Generate LODs** (Optimize tab): reduced copies of every prototype are written as the LOD 1, LOD 2 and Proxy levels of each Prototype Bank row that has no prim of its own for the level (a typed prim always wins). Set the share of triangles of each level (50 / 20 / 5 % by default) and a minimum. Vertex clustering with quadric positions, plain numpy, the same in Houdini 22 and 20.5 / 21; uv, colours and other primvars, transforms and material bindings are carried over; the heroes are never touched. Switch by distance or screen size with the existing Level Of Detail controls.
* New LOD_GENERATOR node (Python LOP) between the source resolver and the compiler; it does nothing with the switch off. New suite `tests/validate_lodgen.py` (8 groups, 5 mutations) and a demo (a ladder of four levels and a field of rocks).

## v1.7.0 - Pick Instance
* **Pick Instance in Viewport** (Finish tab): click an instance in the viewport and its stable id becomes an override row; Ctrl+click ticks Delete as well. A yellow ring marks the instance under the mouse and the prompt shows its id (and its row when it has one). Esc / Enter finishes; every click is one undo step. Instances come from the node's USD stage, so deleted, hidden and not yet grown instances are not pickable. Both builds.
* Selecting the node never starts picking; only the button does. New suite `tests/validate_pick.py` (6 groups, 5 mutations).

## v1.6.2 - Physics tab
* The **Settle** tab is now called **Physics** (the *Physics Settle* switch inside it keeps its name). Parameters and output are unchanged; scenes built with older versions keep their node type and their tab names.

## v1.6.1 - Paint no longer switches the mode by itself
* **Fix:** selecting the Arraytron node (for example after working on another node) entered the Paint viewport tool, which switched *Distribution Mode* to Paint and broke the layout. The tool now never changes the mode: with any other mode it stays idle (nothing drawn, every mouse and key event is left to Houdini) and it wakes up only when the mode is Paint (the *Start Painting* button sets it). Scenes already switched by the old tool need the mode set back by hand.
* The HDA is otherwise identical to v1.6.0 (the suites compare against it); both builds. The paint suite checks the idle behaviour.

## v1.6.0 - Paint shortcuts
* **Paint tool shortcuts:** Ctrl+LMB erase, Shift+LMB relax, Ctrl+Shift+LMB drag sideways = radius, mouse wheel with Shift / Ctrl / Ctrl+Shift = radius / strength / density, keys `[ ]` radius, `- =` strength, `, .` density, `1-4` operation (Add, Remove, Replace, Relax), `F` falloff, `H` help line. Alt and the middle mouse button still navigate.
* A live prompt line shows the brush values (radius, strength, density, falloff, point count); the brush ring changes colour with the operation and a white inner ring shows a strength below 1.
* New suite group 'Brush shortcuts' in `tests/validate_paint.py` (17 groups, 3 new mutations); both builds. The K demo carries the shortcut list in its node comment.
* **Check for Updates:** an *Arraytron* shelf tool installs a newer release from GitHub (`version.json` + zip, SHA-256 checked, nothing runs in the background); `tools/make_update_zip.py` builds the update zip. The HDA itself is unchanged.

## v1.5.0 - Imported Points
* **Paint tool fix (2026-10-15):** the viewport brush follows the mouse (mouse ray from `ui_event.ray()`), a click paints a dab, tool errors show in the viewport prompt. New demo: the letter K painted with the brush (`Arraytron_v1.5.0_paint_k_demo.hip`).
* **Imported Points** (Layout tab, mode 9 in the list): scatter on the points of an FX simulation or any points, from a **SOP node** or a **USD Points / PointInstancer prim** (world space, time samples, time offset); the instances follow the simulation over the timeline.
* Controls: **use percent of points** (stable, only adds), **instance ids** from the source's own id attribute (a particle keeps its prototype, look and overrides), **scale** from `pscale` / `scale` times a multiplier, **orientation** from an orient attribute, along the velocity or from a normal, **copy attributes** from the source.
* **Even Percent** Selection Mode: the Prototype Bank weights become nearly exact percentages for any set of ids (stable per id), with a **Share Of The Points** read-out.
* **IDs for AOVs:** primvars `source_id` and any copied source attribute (besides `arraytron_id`, `prototype_id`, `random`).
* Houdini 22 and Houdini 20.5 / 21 builds with identical output (`tests/validate_h205.py`); new suite `tests/validate_imported.py` (13 groups, 7 mutations) and a demo with 1,800 animated particles. Documentation: `docs/IMPORTED_POINTS.md`.

## v1.1.0 - Houdini 20.5 and 21
* **Houdini 20.5 / 21 build** (`otls_h205/Arraytron_v1.1.0_H205.hda`): the same node on the older Instancer LOP. Houdini 22 keeps its HDA and its behaviour; every suite passes unchanged. The 20.5 / 21 build writes the same PointInstancer (prototype paths, bank order, `protoIndices`, `invisibleIds`, primvars): `tests/validate_h205.py` compares the two on every demo and on an edge-case scene.
* The installer prepares Houdini 20.5, 21 and 22, each with its own build; demos for both (`demos`, `demos_h205`).
* Fixes that came out of the port and also apply to Houdini 22: the debug view no longer uses `Geometry.pointCount()`; the Grow `invisibleIds` are written at the time sample of the instancer when it has one.
* Known limits in 20.5 / 21: restart Houdini after updating the HDA (a re-installed node type loses its parameters there, a SideFX handle-binding problem); no Bullet ground margin; the interface was not checked by eye (headless tests only).

## v1.0.0 - production release
* **Instance overrides** (Finish tab): Delete, Move, Rotate, Scale, Prototype per stable instance id; applied after the physics and before Grow.
* **Paint:** Replace and Relax added to the brush operations.
* **Debug views** (guide purpose, never rendered): generated and rejected points, colour by prototype / id / weight, axes, collision radius, cluster centres.
* **Export USD** (self-contained instances file) and a caching strategy (`docs/CACHING_AND_PIPELINE.md`).
* **Stable-id audit** of every Distribution Mode; **production tests** (saved scene round trip, cross-process determinism, 20,000 point stress, fuzzing, `usdchecker`, script lint, release hygiene).
* Documentation: user guide, index, troubleshooting, handoff; a richer Help tab in the HDA; the installer package (`Arraytron_v1.0.0_Release.rar`) and the DevKit for continuing the work on another PC (`Arraytron_v1.0.0_DevKit.rar`).
* Fixes found by fuzzing: debug and Grow-arrow guides no longer crash when the points fail to cook.

## v0.9.0
* **Optimize tab:** camera optimisation (frustum, distance, density by distance, behind camera; hidden through `invisibleIds`), LOD / proxy prototypes per Prototype Bank row (switch by distance or screen size), extended primvars.

## v0.8.0
* **Cluster** distribution; No Overlap merged into **Separation & Collision** (priority, **Avoid Geometry**).

## v0.7.0
* **Field Stack** (Height, Slope, Noise, Image, Distance, Exclusion; Multiply / Add / Subtract / Min / Max). HDA icon embedded.

## v0.6.0
* Viewport **brush** (Paint mode, Python Viewer State); clearer input sockets; all demos in one scene.

## v0.5.2
* Six-tab interface and the **Grow** animation.

## v0.5.1 / v0.5.0
* **No Overlap**; **Masks** (noise, image, mesh primvar).

## v0.4.6 / v0.4.5 / v0.4.0
* Surface Scatter; Curve; **Physics Settle** (Bullet, cached).

## v0.3.x and earlier
* Prototype Bank, Circle, Variation, Grid, Scale Instances, Bounds Transform with viewport handle (`docs/VERSIONING.md`).
