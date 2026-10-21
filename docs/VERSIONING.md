# Arraytron versioning

Adopted 2026-10-04 (first as zero-padded `vMM.mm.pp`, then simplified the same day to plain numbers at the user's request). The early versions were named ad hoc (0.1, 0.15, 0.16, 0.2, 0.21, 0.3, 0.35), which sorted wrongly in a plain-text file listing (`_` sorts before digits, so `v0.1_demo` landed ahead of `v0.15`) and said nothing about what changed.

## The scheme: `vMAJOR.MINOR.PATCH`, plain numbers
`v0.3.5`, not `v00.03.05`: no zero padding, and any field may grow to two or three digits when it needs to.

| Field | Meaning |
| --- | --- |
| MAJOR | `0` until the 1.0 production release (`v1.0.0`). |
| MINOR | One step of the master roadmap (3 = Prototype Bank, 4 = Curve/Surface/alignment, 5 = masks, ...). |
| PATCH | A small addition or fix inside a step (5 = Circle on top of the Prototype Bank). |

- **File names** use the id: `Arraytron_v0.3.5.hda`, `Arraytron_v0.3.5_demo.hip`, `arraytron_v0.3.5_demo_xpu.png`, `validation_v0.3.5.json`.
- **Houdini type names** use the same dotted numbers: `arraytron::instancer::0.3.5`. Houdini compares each part as a number.
- `tools/versions.py` is the single source of truth: ids, type names, and where every file lives. Builders and tests read it, and it still accepts the older spellings (`v035`, `v00.03.05`) as aliases.
- **Sorting caveat.** Natural-sort file managers (Windows Explorer) order plain numbers correctly at any size. A strictly plain-text sorter only misorders a field once it reaches 10 (`v0.3.10` before `v0.3.2`). The roadmap keeps MINOR at 9 or below until 1.0 and patches are rarely above 9, so this is not expected to matter; if it ever does, only the file names would need padding, not the scheme.

## Layout
`dist/` holds the **current release** only (HDA, demo HIP, USD export) plus `test_assets/` and `manifest.json`. The Houdini 20.5 / 21 build of a release lives in `otls_h205/` as `Arraytron_<id>_H205.hda` (same type name; the builder makes it when run by hython 20.5; older releases have an H205 build there only as the baseline the suites compare against). Every earlier release is in `dist/archive/`. Render previews are in `renders/`, test evidence in `tests/` (`validation_<id>.json`).

## Existing releases
| Id | Was | Houdini type (unchanged for old releases) | What it is |
| --- | --- | --- | --- |
| v0.1.0 | v0.1 | `arraytron::instancer::0.1` | Line + Area, native PointInstancer, whole-distribution transforms (incl. the transform demo) |
| v0.1.5 | v0.15 | `arraytron::instancer::0.15` | Shared Bounds Transform, viewport handle, guide, working Line/Area UI |
| v0.1.6 | v0.16 | `arraytron::instancer::0.16` | Line By Spacing, Keep Inside Area |
| v0.2.0 | v0.2 | `arraytron::instancer::0.20` | Grid / Matrix |
| v0.2.1 | v0.21 | `arraytron::instancer::0.21` | Scale Instances toggle |
| v0.3.0 | v0.3 | `arraytron::instancer::0.30` | Prototype Bank, modular network |
| v0.3.5 | v0.35 | `arraytron::instancer::0.3.5` | Circle / Radial, `p@align` alignment hook |
| v0.3.6 | - | `arraytron::instancer::0.3.6` | Variation extras: Yaw Only, Scale Min / Max, Non-Uniform scale |
| v0.4.0 | - | `arraytron::instancer::0.4.0` | Physics Settle: optional Bullet rigid-body settle of the distribution, cached |
| v0.4.5 | - | `arraytron::instancer::0.4.5` | Curve distribution (BasisCurves from the stage, tangent alignment) |
| v0.4.6 | - | `arraytron::instancer::0.4.6` | Surface Scatter (meshes from the stage, normal alignment, slope limits, density) |
| v0.5.0 | - | `arraytron::instancer::0.5.0` | Mask pipeline (Noise, Image, Mesh Primvar; Density / Scale) |
| v0.5.1 | - | `arraytron::instancer::0.5.1` | No Overlap (Remove Overlapping, Push Apart, Spacing) |
| v0.5.2 | - | `arraytron::instancer::0.5.2` | Six-tab interface (same parameter names) and the Grow animation |
| v0.6.0 | - | `arraytron::instancer::0.6.0` | Viewport brush (Paint mode, Python Viewer State), clearer input labels |
| v0.7.0 | - | `arraytron::instancer::0.7.0` | Field Stack (Height, Slope, Noise, Image, Distance, Exclusion), embedded HDA icon |
| v0.8.0 | - | `arraytron::instancer::0.8.0` | Cluster mode; No Overlap merged into Separation & Collision (Priority, Avoid Geometry) |
| v0.9.0 | - | `arraytron::instancer::0.9.0` | Optimize tab: camera culling, LOD / proxy prototypes, extended primvars |
| v1.0.0 | - | `arraytron::instancer::1.0.0` | Production release: instance overrides, Paint Replace / Relax, debug views, USD export, production tests, documentation |
| v1.1.0 | - | `arraytron::instancer::1.1.0` | Houdini 20.5 / 21 build (`otls_h205/`), installer for 20.5 / 21 / 22; Houdini 22 behaviour unchanged |
| v1.5.0 | - | `arraytron::instancer::1.5.0` | Imported Points: scatter on FX simulation / imported points (SOP or USD), Even Percent selection, source ids and attributes as primvars; both builds |
| v1.6.0 | - | `arraytron::instancer::1.6.0` | Paint tool shortcuts (mouse wheel, Ctrl+Shift drag, keys, live prompt, coloured brush); both builds |
| v1.6.1 | - | `arraytron::instancer::1.6.1` | Fix: selecting the node no longer switches the Distribution Mode to Paint; both builds |
| v1.6.2 | - | `arraytron::instancer::1.6.2` | The Settle tab is called Physics; both builds |
| v1.7.0 | - | `arraytron::instancer::1.7.0` | Pick Instance: click an instance in the viewport to create its override row; both builds |
| v1.8.0 | - | `arraytron::instancer::1.8.0` | Built-in LOD generator: reduced copies of the prototypes as LOD 1 / LOD 2 / Proxy; both builds |
| v1.9.0 | - | `arraytron::instancer::1.9.0` | Instance Place: instances placed one at a time (table + viewport tool); both builds |
| v1.10.0 | - | `arraytron::instancer::1.10.0` | Instance Place arrays: Copies with Copy and Transform style steps; both builds |
| v1.11.0 | - | `arraytron::instancer::1.11.0` | Place tool extras (drag, snap, along curve), node name arraytron1, Settle Instances label; both builds |
| v1.12.0 | - | `arraytron::instancer::1.12.0` | Falloff: scale and density fade towards the edge of the layout, every Distribution Mode; both builds |
| v1.13.0 | - | `arraytron::instancer::1.13.0` | Falloff follows the mode (clusters, paint strokes, 3D grid); tabs Prototypes / Variation / Debugging and a new Export tab; both builds |
| v1.14.0 | - | `arraytron::instancer::1.14.0` | Rows: Line, Circle and Curve in several rows, optionally random; both builds |
| v1.15.0 | - | `arraytron::instancer::1.15.0` | Biome: rule based scatter on a terrain by elevation, slope, moisture and temperature; both builds |
| v1.16.0 | - | `arraytron::instancer::1.16.0` | Biome: an Effect (0 to 1) per condition in every biome row; both builds |
| v1.17.0 | - | `arraytron::instancer::1.17.0` | Mode Palette: the Distribution Mode as a row of icon cells in the Parameters pane; both builds |
| v1.18.0 | - | `arraytron::instancer::1.18.0` | Asset Library (categories, Asset Catalog import, Add to Bank); Stagger Rows as a slider; both builds |
| v1.19.0 | - | `arraytron::instancer::1.19.0` | Biome layers, clearance, exclusion and presets; both builds |
| v1.20.0 | - | `arraytron::instancer::1.20.0` | Painted biome map: a viewport brush that paints where each biome grows or stays out; both builds |
| v1.21.0 | - | `arraytron::instancer::1.21.0` | LOD generator keeps materials and textures (subsets, bindings, no copied shaders); the all-demos scene as a grid; both builds |
| v1.21.1 | - | `arraytron::instancer::1.21.1` | LOD generator on Houdini's own assets (Test Geometry): left-handed meshes get outward normals, instanceable prototypes are cloned; both builds |
| **v1.22.0** (current) | - | `arraytron::instancer::1.22.0` | Position Noise for every Distribution Mode, Display: Points Only, Stagger Rows cycles (a Circle keeps its orbit); both builds |

Old releases keep the type names they shipped with, so scenes built with them still load. Their HDA files were moved bit-for-bit (checked by SHA-256 against the originals) to `dist/archive/`, except v0.3.0 and v0.3.5, which were rebuilt from their builders (v0.3.5 was then moved to the archive with `tools/archive_release.py`, its first real use). A scene of your own that contains old nodes records the old HDA path: install the archived HDA (Assets > Install Asset Library) if Houdini reports the type missing.

Next planned: v0.4.0 Curve / Surface Scatter / alignment, v0.5.0 masks, v0.6.0 brush, v0.7.0 Field Stack, v0.8.0 clustering/collision, v0.9.0 camera/LOD, v1.0.0 production polish (see `docs/MASTER_PLAN_MAP.md`).

## Releasing the next version
1. Add the new id to `tools/versions.py` (`VERSIONS`) and set `CURRENT` to it.
2. Build the HDA and demo (`tools/build_arraytron_v03.py <id>` and `tools/build_demo_v03.py <id>` for the Prototype Bank line; extend their `CONFIG` for new VEX/guide files), validate (`tests/validate_v016.py <id>`, which reads `versions.py`), render a Karma preview into `renders/`.
3. Archive the previous release: `hython tools/archive_release.py <previous id>`. Do not move an HDA by hand: a HIP records its HDA's absolute path, and loading a HIP after its HDA moved degrades the nodes (this happened once during the migration; the tool contains the safe order).
4. Regenerate `dist/manifest.json`, update `STATUS.md`, `README.md` and the table above.

## Legacy scripts
The pre-versioning scripts (`build_arraytron.py`, `build_demo.py`, `build_transform_demo.py`, `build_arraytron_v015.py`, `build_demo_v015.py`, `build_arraytron_v016.py`, `build_demo_v016.py`) still write the old file names into `dist/`; the maintained copies of those releases are the archived files. `tools/migrate_versioning.py` (pass 1, padded ids) and `tools/migrate_versioning_plain.py` (pass 2, plain ids) are the one-off migration records and are not meant to be re-run.
