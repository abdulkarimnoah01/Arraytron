# Paint Engine 2.0 (Arraytron v1.36.0, Arraytron Stamp 0.11.0)

One brush engine for both tools. **Arraytron** paints editable procedural points (they go through Variation, Mask, Separation, Physics like any distribution). **Arraytron Stamp** paints committed stamps you then edit one by one. Both now use the same maths, the same falloff and the same keys where the workflows agree.

## Architecture

| Part | Where | What |
|---|---|---|
| **BrushCore 2.0** | `src/brushcore.py` (pure numpy, no `hou`) | Falloff curves and profiles, presets, the swept-field stroke (`BrushStroke`), distance-based dabs (`BrushDabs`), a hash grid (`BrushGrid`, `bc_pairs`), the brush maths (`bc_erase`, `bc_relax`, `bc_scale`, `bc_push`, `bc_orient`, `bc_replace`, `bc_clone_capture` / `bc_clone_place`), the cursor geometry (`bc_cursor`, `bc_profile_lines`), the brush registry and radial layout (`BC_BRUSHES`, `bc_radial_layout`), the HUD rows and the user preferences (`bc_prefs_*`). |
| Arraytron adapter | `src/arraytron_paint.py` (end of file) | `PaintStroke`, `PaintEditStroke`, the clone functions, the paint data columns, `paint_cast` / `paint_hit` (one `hou.Geometry` per surface). |
| Stamp adapter | `src/stamp_core.py` | `StampPaintStroke` (on `BrushStroke`), `StampEditStroke`, Clone, Restore / Remove Erased. |
| Viewers | `src/arraytron_paint_state.py`, `src/stamp_state.py` | Only events and drawing; they call the adapters. |

Both builders put `brushcore.py` at the top of the HDA's PythonModule, so each HDA still stands alone and installs as before. No third-party Python package is needed.

**Separation of live interaction and committed state.**
- **Arraytron:** a stroke works on the painted points in memory. The viewport shows the dots of the stroke, redrawn at most every 60 ms. The dots are capped at the preview budget of 20 000 (a fixed subset by id) plus the stroke's own points. The paint data is written **once, on release**, as one undo step. Esc during the stroke drops it, and nothing is written.
- **Stamp:** the instances themselves move live, through held-back writes of the Stamps text (at most every 50 ms, slower with more than 5 000 stamps because every write recooks the instancer: once a second at 100 000; and never more than a third of the time). The tool's state undo group makes the whole stroke one undo step. Esc puts the text back.

## Painting (both tools)

A stroke is **one continuous painted region**, not a chain of circles.
- **Candidates** come from a world-fixed jittered grid with one point per `1 / Density` of area. Each cell has its own hash for its jitter, its acceptance threshold and the instance's random numbers.
- **Distance:** a candidate's distance is measured to the **polyline of the whole stroke**. A candidate in a falloff transition waits until the brush has moved a radius past it, so its distance is final.

Because of this:
- The same path gives the same instances at any mouse speed or event rate (Test D).
- There are no dab rings, no round ends inside a stroke, and slow cursor positions don't overpopulate.
- **Revisiting:** painting over a painted area adds nothing beyond the Spacing.
- **Density** means instances per square scene unit in the middle of the stroke. **Spacing** is only the minimum distance between two instances.

**Spray / Spatter:** with Density Randomness 0, Paint is an even spray. With more, the density is patchy, in clumps of about the brush size. The same Seed gives the same clumps.

## The falloff (independent Density and Scale)

Each channel has its own switch and its own profile:

| Setting | Meaning |
|---|---|
| Edge Minimum (%) | The value at the rim of the brush (Density: a share of Density; Scale: a share of the instance's scale). |
| Interior Scale (%) (Scale only) | The scale on the plateau (100 keeps the instance's size). |
| Falloff Width (%) | How much of the radius the fall takes, from the rim inwards (100 starts at the centre, 0 is a hard edge). |
| Falloff Strength (%) | How much of the fall is used. |
| Curve | Linear, Smoothstep, Smootherstep, Ease In, Ease Out, Custom Ramp, Constant (hard edge), Gaussian (a bell scaled to reach 0 exactly at the rim, no clipping step). |

The fall is computed from the distance to the stroke:
- `u = clamp((r - inner) / (1 - inner))`, where `r` is the distance to the stroke divided by the radius, and `inner = 1 - width`.
- `influence = 1 - curve(u)`.
- `multiplier = lerp(min, max, influence)`, then blended with 1 by Strength.

The analytic curves are exact; only the Custom Ramp uses a 257-step table. The multiplier is a pure function of the distance, so evaluating it again never compounds.

**What multiplies what:**
- **Arraytron:** the painted points keep the Scale Falloff in a column of their own (`fall`). The instance scale is the Variation scale × the bank row's scale × `fall` × `edit` (the Grow / Shrink edits).
- **Stamp:** a stamp's scale is its own scale (Uniform × Random) × the Scale Falloff when it is made. The bank row's Scale and Scale Random are applied at the cook.

**Presets** (they only set the parameters above, and every preset is editable):
- Uniform Scatter, Soft Natural, Sparse Edges, Growth, Dense Center, **Hard Stamp**, **Edge Taper**, and **Sparse Organic**, which is the default of a new node: Density smoothstep over 80 %, Scale smootherstep over 55 % down to 25 %.
- F cycles the presets in Arraytron's tool.

## The brushes

| Brush | Arraytron (Paint mode, `paint_op`) | Stamp (`brush`) | Modifiers |
|---|---|---|---|
| Paint / Spray | Add (1) | Paint (Paint tab) | Ctrl: erase |
| Erase | Remove (2): removes points, ids never reused | Erase: switches stamps off (ids stable; Edit tab > Restore / Remove Erased) | Shift: soft thinning (less at the rim, more with every pass) |
| Relax | Relax (4): even spacing towards Min Spacing (or the mean spacing) | Relax | The ring around the brush holds the boundary (the footprint stays) |
| Grow / Shrink | 5: a separate `edit` multiplier (Restore removes it) | Grow / Shrink (on the stamp's scale; Sit On Surface keeps the bottom on the ground) | Ctrl: shrink, Shift: smooth sizes. Grow and Shrink are symmetric (no drift), and a size never reaches 0 |
| Push / Attract | 6 | Push / Attract | Ctrl: attract (never past the centre), Shift: drag along the stroke. Instances stay on the surface at their height above it |
| Replace (Swap) | Swap Prototype (7): to Swap To Row, or by bank Weight | Replace: by the working set (selected cards), by Weight | Position, rotation and scale stay; the same id always draws the same row |
| Orient / Comb | 8: a combed point keeps its heading (the variation's random yaw is dropped for it); Shift: Restore | Orient / Comb | Ctrl: random heading, Shift: Restore (Arraytron) / smooth headings (Stamp). Turns are about the instance's own up, so the surface alignment stays |
| Clone | 9: Ctrl + click picks the points under the brush; click / drag stamps copies | Clone: the same with stamps (prototypes and materials kept) | Shift / Ctrl + wheel: rotate / scale the copy (Stamp); Random Rotate Copies |
| Repaint | Replace (3, the v0.6.0 brush) | - | |
| Mask Paint | Arraytron's mask brush (Paint Mask, v1.26.0 to v1.28.0) is the mask system; it is not duplicated | - | Stamp has no mask (it places by hand) |

The editing brushes act on **dabs every fifth of the radius along the path** (BrushDabs), so their effect per length of stroke does not depend on the mouse speed. Each dab only looks at the instances a hash grid finds under it, so a local edit costs what is under the brush, not the whole population.

Settings:
- **Arraytron:** Layout tab > Paint, with the Basic settings at the top and Advanced > Sculpt Brushes below.
- **Stamp:** Brush > Paint and Brush > Sculpt.

The shared settings are Amount, Brush Falloff (the curve), Hardness and Only The Working Set (Stamp).

## Viewport

- **Cursor:** BrushCore's cursor in the brush's colour: teal Paint, warm orange Erase, blue Relax, cyan Scale, violet Push, pink Replace, gold Orient, green Clone.
  - The radius ring is cast onto the surface, so it follows slopes.
  - Paint shows a ring where each falloff starts, and the two profiles stand on the surface (density on one side, scale on the other).
  - The editing brushes show their Hardness ring.
  - The cursor also has a centre cross and a normal tick.
- **HUD:** Houdini's HUD panel shows the brush's own hints and its live values, written only when they change.
  - **H** cycles Minimal, Standard, Expanded and Hidden.
  - The level is kept for the user in `arraytron_brush_prefs.json` in the Houdini user folder (`ARRAYTRON_BRUSH_PREFS` overrides the path), shared by both tools.
  - In Arraytron, the prompt line keeps one short line.
  - The same file holds `cursor_opacity` (0.1 to 1) and `compact` (true: the radius ring and the cross only, no falloff rings or profiles), and `preview_budget`, the most dots Arraytron draws during a stroke (20 000).
- **C** opens Houdini's radial menu (the Layout tool's mechanism, `SceneViewer.displayRadialMenu`):
  - Main ring: Paint north, Relax, Erase, Grow / Shrink, Push, Clone and Replace around it.
  - **More** in the south holds Orient / Comb plus each tool's own brushes (Stamp: Place, Delete, Group and Edit Mode; Arraytron: Repaint).
  - Without radial menus, a popup at the cursor.

### Keys (context-aware; existing shortcuts kept)

| Input | Arraytron Paint (Continuous Stroke) | Arraytron Stamp 0.11.0 |
|---|---|---|
| LMB drag | the brush | the brush (Place: click / drag sets rotation and scale) |
| Ctrl + LMB | Paint: erase; sculpt: the variant above | Paint: erase; sculpt: the variant; Place: orient; Clone: pick the source |
| Shift + LMB | Add: Relax (as before); sculpt: the variant | sculpt: the variant; Place: scale only |
| Ctrl + Shift + LMB drag | brush radius (as before) | Place: orient freely |
| wheel | camera (as before) | cycle the working set (Place, Paint, Replace) |
| Shift + wheel | radius | radius (Paint, sculpt) / scale (Place) / Clone rotate |
| Ctrl + wheel | strength | density (Paint) / strength or amount (sculpt) / rotation (Place) / Clone scale |
| Ctrl + Shift + wheel | density (Add) / amount (sculpt) | - |
| `[` `]` | radius | radius (Paint, sculpt) / scale (Place) / Clone scale |
| `-` `=` | strength | strength (Paint, sculpt) |
| `,` `.` | density | rotate the next stamp |
| `1` - `9` | the brush | the prototype row (as before; brushes are on C) |
| C / B | radial brush menu / - | radial brush menu / options menu |
| H | HUD level | HUD level |
| F | next falloff preset | - |
| Esc | during a stroke: cancel it; else leave | during a stroke: cancel it; else leave |
| Shift + B, Del, Z, G, M | (Edit tool) | as before |

C and H are hotkeys of each tool's state (Hotkey Editor: the Arraytron Paint and Arraytron Stamp operations), so Houdini's own C radial menu stays outside the tools and you can rebind them. The two tools differ only where their workflows do. `1` to `9` choose prototype rows in Stamp, as they always have. Arraytron has no prototype under the brush, so there `1` to `9` choose the brush.

## Compatibility and rollback

- **New versions:** `arraytron::instancer::1.36.0` and `arraytron::stamp::0.11.0`. Saved scenes keep their v1.35.0 / 0.10.0 nodes, which still load.
  - v1.35.0 is archived under `dist/archive` with its demos; its Houdini 20.5 build stays in `otls_h205`.
  - Stamp 0.10.0 stays next to 0.11.0.
- **Rollback:** install the previous release (GitHub release v1.35.0 / stamp-v0.10.x), or switch a node back to its old version.
- **Paint data:**
  - Old texts (`p1`, `p2`) read as before. The new columns default to fall 1, edit 1, yaw 0, not combed, prototype auto.
  - A paint without edits is still written as `p1` / `p2`, bit for bit.
  - The `p3` text adds the five columns and the stroke paths.
  - An older Arraytron cannot read `p3`. Only nodes of v1.36.0 write it.
- **Classic Dabs** (Advanced > Brush Engine) is the v0.6.0 brush of Arraytron, exactly: Add, Remove, Replace, Relax, the prompt line and its keys. `tests/validate_paint.py` still checks it.
- **Stamp's Classic Dabs** keeps the 0.9.3 rule: the swept field only with a falloff on.
- **Stamp's ids:** the Stamps text format is unchanged. Erase switches stamps off instead of removing lines, so the ids (line numbers) of the others stay. The Delete brush and Remove Erased still renumber, as before.
- **Arraytron's VEX:** the variation stage of v1.36.0 (`src/vex_v1360`) drops the random yaw of a combed point (`i@paint_combed`). It is the only VEX change. Older versions use their own VEX folders, untouched.
- **Limits:**
  - Arraytron paints up to 200 000 points, up from 20 000.
  - The Stamp has no limit of its own; a parameter write costs as long as the text is long.

## Tests and evidence

- `tests/validate_brushcore.py`: the maths without Houdini, 105 checks. The mutations `bc_curve`, `bc_rate`, `bc_spacing`, `bc_grid`, `bc_relax`, `bc_scale`, `bc_dabs` and `bc_orient` each make it fail. Tests A to F and I run on the pure engine.
- `tests/validate_paintengine.py`: both HDAs end to end, 82 checks.
  - Tests A to D and I on the node.
  - Instances: the scales, the combed headings despite a random yaw, Swap, Erase ids, Relax and Push on a terrain (Tests E and G).
  - Clone, and the Stamp's sculpt brushes on the Stamps text.
  - Both viewer states through a stand-in viewport: one write and one undo step per stroke, Esc, H, C, F, `1` to `9`.
  - The mutations `fall`, `comb`, `erase_ids`, `stamp_erase`, `cancel` and `swap` each make it fail.
- `tests/validate_paint.py` (Classic Dabs) and `tests/validate_stamplite.py` (Stamp 0.11.0, 367 checks) pass.
- **Performance:** `docs/PAINT_ENGINE_2_PERFORMANCE.md` (`tools/bench_paint_engine.py`, `tools/report_paint_bench.py`).
- **Demo:** `Arraytron_v1.36.0_paintengine_demo.hip` (`tools/build_demo_paintengine_v1360.py`). It shows soft density, soft scale, combined, Relax, Grow / Shrink, Push / Attract, a stroke over a hill, and the Stamp row.

**Not verified by hand:**
- The brushes under a real mouse.
- How the cursor, the HUD levels and the radial menu look in a real Scene Viewer.
- The radial menu itself; a real viewer is needed for it.
- The hotkey binding of H in the Stamp's Hotkey Editor context.
- Houdini 21, which can't run hython on this machine.

Benchmarks measure the Python side of the tools, not the GPU drawing.
