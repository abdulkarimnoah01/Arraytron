# Houdini 20.5 / 21 build (v1.1.0)

Status 2026-10-12: **done and tested headless** (hython 20.5.445 and 21.0.440; Houdini 22.0.368 stays the reference). v1.1.0 ships two builds of the same node, `arraytron::instancer::1.1.0`: the Houdini 22 HDA (`dist/Arraytron_v1.1.0.hda`) and the Houdini 20.5 / 21 HDA (`otls_h205/Arraytron_v1.1.0_H205.hda`, built with hython 20.5 and loaded unchanged by 21). Nothing in the Houdini 22 build's behaviour changed; every suite passes unchanged against v1.0.0. What is **not** verified: anything that needs the interface (GUI) in 20.5 / 21, the same list as for Houdini 22 (tabs, Paint tool in a real viewport, debug guides, icon, handle dragging, the Simulate & Cache dialog).

## Why a second build

Houdini 22 has the `pointinstancer` LOP. Houdini 20.5 and 21 do not (probe: `tools/probes/node_types_check.py`; of the 101 node types in the v1.0.0 network only `pointinstancer` was missing). They have the older `instancer` LOP (`method` = `pointinstancer`, internal SOP network, prototype index by `pathattr`). Two differences from Houdini 22 matter and were measured (`tools/probes/instancer_probe_h205.py`): the older instancer **sorts** the prototype list (Barrel before Crate although the pattern said Crate Barrel) and it copies a prototype to `<output>/Prototypes/<its full source path>` (`/World/Arraytron/Prototypes/World/Props/Crate`), where Houdini 22 writes `<output>/Prototypes/Crate` in bank order.

## How the build works (one source tree)

`tools/build_arraytron_v03.py` is the only builder. It builds the Houdini 20.5 / 21 variant when it is run by a hython older than 22 (`versions.is_h205()`; the environment variable `ARRAYTRON_TARGET=h205|h22` forces it) and writes `otls_h205/Arraytron_<ver>_H205.hda`. In that variant the compiler part differs, everything else (all VEX, all Python SOPs, every parameter, the guide, the viewer state) is the same:

| Piece | Houdini 22 | Houdini 20.5 / 21 |
| --- | --- | --- |
| Compiler node `USD_COMPILER` | `pointinstancer`, prototypes copied from the bank prims in the stream | `instancer`, prototypes copied from the **second input** |
| Second input | - | `PROTO_STAGE` (`src/proto_stage_h205.py`): one top-level prim per prototype (`/Crate`, `/Barrel`, `/Rock`, `/Rock2`) that **specializes** the bank prim, untyped so a Cube or Cone source keeps its type; this makes the copies land at `<output>/Prototypes/<name>` exactly like Houdini 22 |
| Prototype per point | integer `protoindex` | string point attribute `protopath` (last SOP `PROTO_PATH`, `sop_protopath` in `src/arraytron_h205.py`), the instancer's `pathattr` |
| After the instancer | - | `PROTO_NORMALIZE` (`src/proto_normalize.py`): puts the prototype targets back in bank order (hero prototypes, then LOD / proxy prims) and remaps `protoIndices` and the child order, and hides the source prims like Houdini 22's `hideprotosourceprims` |
| Grow's `invisibleIds` | the importer's `importinvisids` is switched off while Grow is on | the older instancer writes an (empty) time sample of `invisibleIds`; the guide script (`src/guide_bounds_v052.py`) writes its list at that sample's time so it is not shadowed |

The result: prototype index k is bank ordinal k in both builds, so the camera LOD table, the overrides, the tests and the USD a farm reads do not depend on the Houdini version. `tools/build_h205_all.sh` builds the v1.1.0 HDA and the older baselines the suites compare against; `tools/build_h205_demos.sh` builds the demo scenes.

## Known differences and Houdini 20.5 / 21 specifics

* **Handle bindings and reloading (SideFX).** In 20.5 and 21 a node type whose DialogScript has `bindhandle ... lopxform ...` lines (the viewport gizmo for the Bounds Transform) comes back **without any parameters** if its library is unloaded and installed again in the same session (`hou.hipFile.clear`, opening another scene that recorded the library, `uninstallFile`). Houdini 22 only prints a warning. In normal use the package loads the HDA once at startup and nothing unloads it. The demo scenes of this build are therefore saved without a library record (they use the packaged HDA, `versions.ensure_installed`; opening several demos in one session was tested in 20.5 and 21), and the test suites install a copy without the bindings (`tools/h205_compat.py`, automatic in every `validate_*` script); the shipped file's bindings are checked in a clean session by `tests/validate_h205.py`. If a node ever shows few parameters, restart Houdini.
* The Bullet solver of 20.5 / 21 has no `ground_margin`; the other margins are set. Physics results are not bit-identical to Houdini 22's (they never were across Bullet builds); the physics suite (19 groups) passes in 20.5 and 21.
* `node.cook(force=True)` raises `hou.OperationFailed` when the cook errors (Houdini 22 returns), and `node.errors()` reports the last cook; the tests recook and catch it. `hou.Geometry.pointCount()` does not exist before 22: the debug view uses `intrinsicValue('pointcount')` in both builds.
* `usdchecker` is a `.cmd` wrapper in 20.5 / 21 (no `.exe`); the production suite handles both.
* Scenes saved with the Houdini 20.5 build open in Houdini 22 against the Houdini 22 node of the same version and cook the same (tested with three demos, hython). A Houdini 22 scene cannot be opened by 20.5 / 21 (Houdini's own rule).

## Evidence (HYTHON level unless noted)

* hython 20.5.445 and 21.0.440 with the 20.5-built HDA: main 39 groups, physics 19, scatter 24, mask 11, overlap 6, grow 8, paint 16, fields 16, cluster 8, avoid 7, camera 9, polish 9, production 7. The groups that compare with a previous release use the Houdini 20.5 builds of those releases (`otls_h205/Arraytron_v0.3.0_H205.hda` to `v1.0.0`, built from the same builder).
* `python tests/validate_h205.py` (plain Python, starts hython 22, 21 and 20.5): the shipped HDA installs in a clean session with 324 parameters, 12 handle bindings and a clean default cook in 20.5 and 21; the nine demo scenes and an edge-case scene (two sources with the same name, a top-level source, Cube and Cone sources, USD file, SOP, input connection) are dumped by each Houdini and compared with Houdini 22: positions, scales, orientations (half precision, 2e-3), ids, `protoIndices`, `invisibleIds`, prototype targets, order, types and visibility, hidden sources, primvars, custom data, child prims. Four mutations (`ARRAYTRON_H205_MUTATE=normalize|protopath|hide|stage`) each make it fail.
* Installer: `tests/validate_installer.py` installs the package into a sandbox and checks a clean 22.0, 21.0 and 20.5 session (package per Houdini with its build folder, node found from the right build, installed all-demos scene cooks, several demos opened one after another keep their parameters in 20.5 / 21, update, uninstall).

## Where things are

* Sources: `src/arraytron_h205.py` (module part), `src/proto_stage_h205.py`, `src/proto_normalize.py`; builder branch `if H205:` in `tools/build_arraytron_v03.py`; `tools/versions.py` (`is_h205`, `hda(vid)`, `stem`, `demo_file`, `ensure_installed`, the `h205` flag per release, `BUILD` = `ARRAYTRON_VERSION`); `tools/h205_compat.py`; `tools/demo_compat.py` (Karma settings LOP differs); probes in `tools/probes/`.
* Files: `otls_h205/` (HDAs, demos, `test_assets` copy, `arraytron_cache` for the 20.5 physics demos; the installer ships it as `h205/otls` and `demos_h205`).
* Commands (hython 20.5.445 for the Houdini 20.5 / 21 build; the suites take `v1.1.0` and pick the build from the Houdini that runs them):

```
bash tools/build_h205_all.sh                    # HDAs (never while a suite runs)
bash tools/build_h205_demos.sh                  # demo scenes, physics caches (minutes)
bash tools/run_suites.sh "<hython 20.5 or 21>" v1.1.0 out v016 mask overlap scatter avoid cluster fields grow paint camera polish physics production
python tests/validate_h205.py v1.1.0            # 22 against 21 and 20.5
```

## Not done / ideas

* GUI verification in 20.5 / 21 (see above). Houdini 21.5 and later 21.x are untested; the installer enables the Houdini 20.5 / 21 build below 22.0.
* Karma renders were not re-made for this build (the render USD of each demo is written; `tools/render_demo.py` needs a GPU and the Karma settings LOP of the running Houdini).
* The cross-version comparison covers the demos and one edge scene; physics output is compared by the suite's own invariants, not by value.
