# Paint falloff (Arraytron Stamp 0.9.3): technical notes

A Density channel and a Scale channel for the Paint brush, driven by one spatial field over the whole stroke. This is the short technical changelog: what changed, how it works, what was measured, and what is not verified.

## What changed

| Where | Change |
|---|---|
| `src/stamp_core.py` | `falloff_curve`, `falloff_lut`, `stamp_falloff_profile`, `falloff_multiplier` (the maths); `StampPaintStroke` (the incremental swept-field engine); `stamp_paint_lines`, `stamp_append_lines`, `stamp_paint_path` (batch writes, a whole stroke from a script); `stamp_paint_preset`, `stamp_paint_active`, `stamp_falloff_text`. `stamp_make` seeds modulo 2^32. |
| `src/stamp_state.py` | Paint uses the engine while Density or Scale Falloff is on (one `move` per mouse position, `finish` at the end of the stroke, still one undo group). Viewport feedback: rings at the inner edge of each fall, the two profiles standing on the surface, a HUD line. |
| `tools/build_stamp_light.py` | Paint tab: Falloff (Preset, Enable Density Falloff, Enable Scale Falloff), Density Profile, Scale Profile (Edge Minimum, Center Maximum for scale, Falloff Width, Falloff Strength, Curve, Custom Ramp). |
| New | `tools/build_demo_paintfalloff.py`, `tools/profile_paint_falloff.py`, 32 checks in `tests/validate_stamplite.py` (group `falloff`, plus viewer and speed checks). |

Compatibility: both channels are off by default, and with both off the Paint brush is the classic dab brush, unchanged (including the Edge Falloff parameter, now labelled *classic*). With either channel on, the Density Profile replaces the classic Edge Falloff, which is then ignored. Existing stamps are never touched; falloff only decides the stamps a new stroke makes. The Group brush is unchanged; the maths is in plain functions, so a Group Paint mode can use it.

## The maths

* `r = clamp(distance to the stroke / radius, 0, 1)`, the distance to the **polyline of the whole stroke**, not to a dab.
* `inner = 1 - Falloff Width`, `u = clamp((r - inner) / (1 - inner))`, `influence = curve(u)` (1 on the plateau, 0 at the rim).
* `multiplier = lerp(Edge Minimum, Center Maximum, influence)`, then `1 + Strength * (multiplier - 1)`. Density's maximum is 1.
* Curves: Linear, Smoothstep, Smootherstep, Ease In, Ease Out, Custom Ramp (left of the ramp is the rim, right the inner edge; default a straight ramp). They become a 257 step lookup table once per stroke.
* `final scale = stamp scale x Scale multiplier`; the stamp scale already has Uniform Scale and Random Scale; the bank row's Scale and Scale Random are applied by the cook on top. Sit On Surface and Offset use the final scale.

## How a stroke is made

1. **Candidates** are the points of a world-fixed jittered grid in the plane of the two axes that are not the dominant axis of the surface normal where the stroke began (the ground: X and Z), one per cell of area `1 / Density`. Each cell has a hash (Seed, cell) that gives its jitter, its acceptance threshold and its own random number for the stamp (prototype, rotation, scale). The same cell gives the same numbers whatever order the stroke reaches it in.
2. **The field** is evaluated for the candidates near the new part of the path only (a capsule of the new segment): the distance to the polyline is a vectorised point-segment distance restricted to the segments near the candidates.
3. A candidate **is made** when its threshold is below the Density multiplier at its distance (so thinning is statistical and nested), is scaled by the Scale multiplier, and is cast onto the surface along the axis (not onto stamps). Kept when no stamp, old or new, is closer than **Spacing**, measured in the plane of the stroke (so Sit On Surface and Offset do not matter).
4. A candidate inside the plateau of every channel is made at once (nothing can change it). One in the transition waits until the brush has moved a radius past it, so its distance is final, or the stroke ends. This is why the soft edge does not depend on the speed of the mouse and the middle of the ribbon appears under the cursor.
5. The new stamps are buffered and written with one parameter write; writes are spaced at least 50 ms apart and never take more than a third of the time (the write costs as long as the whole Stamps text); the end of the stroke writes the rest.

Consequences, all tested: the same stroke at any mouse speed makes the same stamps; the same Seed and path make the same stamps; painting over the same place adds nothing (the Spacing); no circles at dabs (there are no dabs); density is exactly the Density setting on the plateau (the classic brush piles up in the overlaps).

Known limits: the grid plane is chosen from the surface normal at the start of the stroke (right for ground and hills; a stroke that goes over a vertical wall is spread by the plane distance there); distances are measured in that plane, not along the surface; a transition candidate appears up to one radius behind the cursor.

## Measured

`hython tools/profile_paint_falloff.py` (writes `tests/profile_paint_falloff_<22|205>.json`). Intel Core i9-13900K (32 threads), 128 GB, Windows 11, Houdini 22.0.368 (Python 3.13) and Houdini 20.5.445 (Python 3.11). Brush radius 2, Density 3, Spacing 0.3, Soft Natural, a prototype of 200 000 triangles in the bank, 400 mouse positions along a long stroke (about 1200 stamps made), Sit On Surface on. Milliseconds per mouse position (what the tool pays for each move), mean (95th percentile):

| Stamps already there | Houdini | New brush, writes held back (the tool) | New brush, a write at every move | Classic dab brush (per dab) |
|---|---|---|---|---|
| 300 | 22 | 2.6 (4.1) | 13.6 (19.2) | 31.4 |
| 3 000 | 22 | 2.6 (7.2) | 9.7 (11.4) | 19.3 |
| 10 000 | 22 | 1.8 (2.1) | 18.5 (21.0) | 32.5 |
| 3 000 | 20.5 | 1.4 (2.5) | 7.5 (9.0) | 16.4 |
| 10 000 | 20.5 | 1.6 (2.1) | 14.0 (15.6) | 28.5 |

* The surface read after a write (it only reads the new stamps): 0.3 to 1.7 ms. The first read of the scene with the 200 000 triangle prototype: 185 to 416 ms, once.
* Painting the same stroke again over 12 414 existing stamps: 0 stamps added, 155 ms for the whole stroke (400 positions).
* The cost of a write is the length of the text: about 45 ms for a Stamps parameter of 10 000 stamps in an earlier measurement, which is why the writes are held back; the spikes in the 95th percentile and the maximum are those writes.
* The measurements vary by a few milliseconds from run to run; they are one machine, not a guarantee.

## Verified and not verified

* **Validated:** `tests/validate_stamplite.py` in Houdini 22 and 20.5 (the maths, the curves, the custom ramp, uniform compatibility, density only, scale only, both, Center Maximum, plateau, strength, speed independence, determinism, the Spacing on repeated strokes, existing stamps unchanged, seating on the ground and on a slope, prototype weights and the stamp cycle, the presets, the viewer state through a stand-in viewport: live stamps, one undo group, rings, HUD, held-back writes). Mutating the multiplier makes the suite fail.
* **Real session:** the Paint Falloff demo was merged into a running Houdini 20.5.445 with its interface, the six Stamp nodes cooked without errors with the expected stamp counts and scales, and the nodes were removed again.
* **Not verified by hand:** the feel of the brush under a real mouse in the viewport, the look of the overlay (rings and profiles) in a viewer, and the Paint tab of the parameter dialog (the Custom Ramp editor in particular). Houdini 21 was not run for this change (its hython crashes with a clean preferences folder on this machine).
