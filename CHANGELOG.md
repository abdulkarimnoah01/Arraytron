# Arraytron changelog

Newest first. Versions are plain `vMAJOR.MINOR.PATCH`; every release is its own node type `arraytron::instancer::<version>`. Each release reproduces the previous one exactly with its new features off (tested). Details: `docs/VERSIONING.md`, `STATUS.md`, `docs/DECISIONS.md`.

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
