# Viewport brush and the clearer inputs (v0.6.0)

## What you wire where

| Input | Label in Houdini | What goes in |
| --- | --- | --- |
| 1 | **Scene Stream: terrain, curve, models** | Your scene: the terrain / ground to paint or scatter on (Surface Prim, Paint Target), the curve (Curve Prim) and any models you want to pick by prim path. |
| 2, 3, 4 | **Input 2 / 3 / 4: extra prototype (optional)** | One extra model each (a Reference, a SOP Create ...). In the Prototype Bank choose Source Type *Input Connection* and Input 2 / 3 / 4. They are merged into the stream, so Prim Path also finds them. |

The hint under the Source tab says the same. A **curve is not a separate input**: put it in the scene you wire into input 1 (a Curves / BasisCurves prim) and type its path into *Curve Prim*.

## The brush

Layout tab, Distribution Mode **Paint**, then **Start Painting** (or select the node and press Enter in the viewport).

| Control | Meaning |
| --- | --- |
| Drag | Adds points under the brush, projected onto the Paint Target (the first hit along the brush normal, so it follows hills). |
| Ctrl-drag | The opposite of the Operation menu: erases. |
| `[` `]` | Smaller / larger brush radius. |
| Esc / Enter | Leave the tool. |
| Paint Target | A prim in the Scene Stream (mesh or basic shape, or a prim above several). Empty = an invisible ground plane at Y = 0. |
| Operation | Add or Remove for a plain drag. |
| Brush Radius, Brush Strength | Disc size; chance that a candidate is kept (Add) or a point is removed (Remove), times the falloff. |
| Density, Min Spacing | Candidates per area for every dab; no two painted points closer than the spacing (so scrubbing back and forth saturates instead of piling up). |
| Falloff | Linear, Smooth, Gaussian, Hard. |
| Seed, Align to Normal, Offset | Seed of the brush's random choices; tilt of the instances; shift along the normal. |
| Clear Paint | Removes every painted point (undoable). |

The painted points are stored in the hidden parameter `paint_data` (compressed float32 positions and normals plus ids, at most 20,000 per node, about 28 bytes a point before compression). Points keep their **id**, so erasing some never renames the others, and everything keyed on the id (variation, mask, No Overlap, Grow, Physics Settle) stays put. New ids never reuse removed ones. The strokes are deterministic: the same dabs and seed give the same text bit for bit.

Everything after the generator works on painted points as on any other distribution: Variation, Mask, No Overlap, Physics Settle, Grow and the Bounds Transform (which moves the painted layout like any other).

## How it is built

* `src/arraytron_paint.py` (in the PythonModule): stroke storage, `falloff_weight`, `brush_add`, `brush_remove`, ray / triangle test, `make_projector`, the Paint generator (`sop_paint`, Python SOP `generate_paint`, switch input 6), `paint_start` / `paint_clear`.
* `src/arraytron_paint_state.py`: the Python Viewer State (HDA section `ViewerStateModule`, state name `arraytron_paint_v060`, `DefaultState` section so Enter enters it). It only handles the mouse and drawing, and writes `paint_data` once on mouse release (one undo step); while dragging it draws a preview of the points and the brush circle.
* Demo: `dist/Arraytron_v0.6.0_paint_demo.hip` (firs painted along an S path, a clearing erased, a small grove, a few crates) and `renders/arraytron_v0.6.0_paint_demo_xpu.png`. The strokes there are scripted with the same functions; open the node and press Start Painting to continue by hand.
* `dist/Arraytron_v0.6.0_all_demos.hip` holds every demo as a separate network box in one scene (`tools/build_demo_all.py`).

## Evidence

`tests/validate_paint.py` (16 groups): the interface (mode 6, the folder under its own heading, buttons, hidden data, embedded state sections, input labels, **every v0.5.2 parameter unchanged**), modes 0 to 5 identical to v0.5.2, storage round trip and damaged data, falloff curves against independent formulas, Add (density, strength, determinism, seed, stable ids, earlier points untouched), falloff shapes, minimum spacing by brute force and saturation, Remove (exactly the points inside, ids kept, never reused), ray test and projection onto a tilted plane (exact), a dome, the ground plane and a missing prim, the node end to end (positions, ids, alignment, offset, erase keeps ids, Clear, Variation and No Overlap on top), identical text for identical strokes, and **the viewer state driven by scripted mouse events through a stand-in viewport** (stroke, drag, commit once on release, hover, Ctrl erase, bracket keys, a click that misses, exit). Six mutations (`ARRAYTRON_MUTATE=paint_falloff|paint_spacing|paint_project|paint_remove|paint_seed|paint_ids`) each fail it. The main (39), physics (19), scatter (24), mask (11), overlap (6) and grow (8) suites pass on v0.6.0. The stand-in test found one real bug (the commit call lacked its data argument).

## Not verified (needs your Houdini)

How the tool feels in a real Scene Viewer: that the node's state is entered by Start Painting and by Enter, that the brush circle and the green preview points draw, that mouse ray picking lines up with the viewport (the stand-in uses an orthographic ray straight down; the real code uses `mapToWorld` of the viewport), that `[` `]` reach the state, that camera navigation (Alt / middle mouse) still works, undo behaviour, and the speed of a long stroke on a dense terrain (each dab tests triangles near the brush only, but the first pick tests every triangle; very large meshes may feel slow).

## Limits

20,000 painted points per node; one set of strokes per node (no paint layers yet); points are stored in world space, so changing the Paint Target afterwards does not re-project them; the brush paints on one target surface.

## Fix after the first real GUI test (2026-10-15)

The first test in a real Scene Viewer showed the brush stuck in the middle and no painting. The state now takes the mouse ray from `ui_event.ray()` (as Houdini's own Paint Instances state does), a plain click paints one dab, and any error in a state callback is shown in the viewport prompt (and printed to the Houdini console) instead of being swallowed. Reload the HDA (reopen the hip or restart Houdini) to get the new state. The viewport behaviour is still not verified by a test: only by looking at it. A Paint-only demo, the letter K painted with the brush functions, is `dist/Arraytron_v1.5.0_paint_k_demo.hip`.

## Shortcuts (v1.6.0)

The tool is driven by the mouse with a few keys; the table is in `docs/USER_GUIDE.md` (section 6). In short: **LMB** paints, **Ctrl+LMB** erases, **Shift+LMB** relaxes, **Ctrl+Shift+LMB drag sideways** changes the radius, the **wheel** with **Shift / Ctrl / Ctrl+Shift** changes radius / strength / density, `[ ]` radius, `- =` strength, `, .` density, `1 2 3 4` the operation, `F` the falloff, `H` the help line. The prompt line shows the live values (radius, strength, density, falloff, point count) and, until `H` hides it, the shortcuts; the brush ring changes colour with the operation (orange Add, red Remove, blue Replace, green Relax) and a white inner ring appears when the strength is below 1. Alt and the middle mouse button always navigate the camera, and a plain wheel zooms as usual. The shortcuts are checked through the stand-in viewport (`validate_paint.py`, group 'Brush shortcuts', three mutations); how they feel in a real viewport is for the user to judge. Demo: `dist/Arraytron_v1.6.0_paint_k_demo.hip` (the letter K; the node comment lists the shortcuts).
