# Position noise and the Points Only display (v1.22.0)

## Noise (Layout tab, section NOISE)
Every Distribution Mode (Line, Area, Grid, Circle, Curve, Surface, Paint, Cluster, Imported, Place, Biome) can move its points with noise. The stage sits right after the distribution and the Rows, before the Mask, the Field Stack, the Falloff and everything else, so those work on the moved points. Ids and the number of points never change.

| Parameter | What it does |
|---|---|
| Position Noise | Off by default: the points are exactly as the distribution made them (the same result as v1.21.1). |
| Noise Type | **Perlin** and **Simplex**: smooth, neighbouring points move alike (the pattern follows the position). **Random (per point)**: every point moves on its own, keyed on its stable id. **Curl (flowing)**: swirling noise. |
| Amount (X Y Z) | How far a point may move on each axis, in the local units of the layout. **Set an axis to 0 and it stays exactly where it was.** The default (0.5, 0, 0.5) moves points on the ground and keeps their height. A point never moves further than the Amount on any axis. |
| Frequency | Size of the pattern (0.5 repeats about every 2 units; higher is finer). Not used by Random. |
| Octaves, Roughness | Layers of finer noise on top (turbulence); Roughness is how strong each finer layer is. |
| Pattern Offset | Slides the pattern through space (animate it for moving noise). |
| Noise Seed | A different pattern per seed. |

The noise is sampled at the position the point had before it moved, so the pattern is the same whatever mode made the points (two lines that share a point move that point the same way). Surface mode: noise on Y lifts the points off the surface, use Amount 0 on Y to keep them on it.

## Display: Points Only (Debugging tab)
**Display** has two settings. *Instances* is the normal result. *Points Only* hides every instance (all ids go into the invisibleIds of the instancer) and draws the points that scatter them as guide points (`<output>/Debug/Final`, purpose guide: visible in the viewport, never rendered), so you see the layout without the models. **The render shows nothing while this is on**, so switch it back before rendering. The points follow the layout transform, the Mask, Falloff, Rows, Noise and everything else because they are the final points. Colour (Colour Final Points By) and size (Debug Size) come from the Debug options; Debug Views can add the generated and rejected points, the axes and so on on top.

## Stagger Rows cycles (Rows section)
Stagger Rows above 1 now cycles: 1.5 is 0.5, 7.85 is 0.85, a whole number is off (the points line up). In a **Circle** the odd rings are turned about the centre by that fraction of the angle between two neighbours, with their facing, so they stay on their orbit (before, the shift was a straight line along the tangent and the points drifted outward). Line and Curve shift along the path as before.

Evidence: `tests/validate_noise.py` (7 groups, 9 mutations) and `tests/validate_rows.py` (7 groups, new mutations `rows_wrap`, `rows_orbit`). Demo: `dist/Arraytron_v1.22.0_noise_demo.hip`.
