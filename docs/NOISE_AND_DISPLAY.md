# Position noise and the Points Only display (v1.22.0)

## Noise (Variation tab, section NOISE; Layout tab before v1.24.0)
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

**New types (v1.24.0).** Value (smooth interpolated randomness, gentle deformation), Alligator (irregular cellular-looking, rocky organic displacement), Worley / Cellular (organic cells and clusters), Voronoi (cell borders, fractures), Ridged Multifractal (sharp crests and valleys, mountains and wrinkles), Billow (rounded puffy formations, clouds and terrain), Turbulence (layered chaotic patterns, erosion), FBM (multiscale natural variation, landscapes), Domain Warp (twisted swirling patterns, complex masks), Flow (smooth patterns that evolve as Pattern Offset X changes) and Periodic (repeats seamlessly every **Period**, rounded to whole noise cells). They share Frequency, Octaves, Roughness, Pattern Offset, Seed and the Amount per axis; a point never moves further than its Amount.

The noise is sampled at the position the point had before it moved, so the pattern is the same whatever mode made the points (two lines that share a point move that point the same way). Surface mode: noise on Y lifts the points off the surface, use Amount 0 on Y to keep them on it.

## Display: Points Only (Debugging tab)
**Display** has two settings. *Instances* is the normal result. *Points Only* hides every instance (all ids go into the invisibleIds of the instancer) and draws the points that scatter them as guide points (`<output>/Debug/Final`, purpose guide: visible in the viewport, never rendered), so you see the layout without the models. **The render shows nothing while this is on**, so switch it back before rendering. The points follow the layout transform, the Mask, Falloff, Rows, Noise and everything else because they are the final points. Colour (Colour Final Points By) and size (Debug Size) come from the Debug options; Debug Views can add the generated and rejected points, the axes and so on on top.

**Boxes and Spheres (v1.24.0)** work the same way but draw one shape per instance instead of a point: a box with the size and place of the bound of its prototype, or a sphere around that bound, turned and scaled like the instance and coloured by prototype (guide purpose, never rendered). Use them to check size, spacing and overlap of the whole scatter without the cost of the models.

## Visualize colours, palettes and the Mask noise types (v1.25.0)
The Visualize display can paint **vertex colours** on a copy of the scattering surface (*Surface Style*: Vertex Colours, Dots, Both; *Surface Resolution* is the number of small triangles the copy is cut into). *Palette* picks the colours (Blue to Yellow, Heat, Viridis, Magma, Rainbow, Grayscale, Red Yellow Green, Cool to Warm, Terrain, or **Custom Gradient** with its own ramp). *Range* stretches a small span of values over the whole palette and *Surface Opacity* lets you see the ground through the colours. The instances use the same palette and range. The Mask and Noise sections only have a Visualize menu; the palette settings are in the Debugging tab.

The **Mask Source Noise** has a *Noise Type* menu (Perlin, Simplex, Random, Curl, Value, Alligator, Worley, Voronoi, Ridged, Billow, Turbulence, FBM, Domain Warp, Flow, Periodic). Value is the default and the original mask noise. The section that moves the points is called **Noise Positional Shift**.

## A new node is a test run (v1.25.0, ground plane since v1.25.1)
A node created in the interface with nothing wired in, with the mode and Prototype 1 still at their defaults, becomes 30 built-in spheres scattered (Surface mode) on a built-in flat 10 x 10 test ground plane, so it shows something at once. The plane (`/World/TestGround/Plane`) is added to the stream while **Built-in Test Ground** (Prototypes tab, TEST SETUP) is on. The button **Start From Test Setup** does the same on any node. Wire a real surface and switch the ground off, or change Prototype 1 and Surface Prim, to use your own. The HDA works with no input; wiring one works as before. Nodes made by scripts keep the plain defaults.

## Visualize (v1.24.0)
Debugging tab, section VISUALIZE: *Visualize On* (Off, Scattering Surface, Instances, Both) and *Visualize* (Mask, Field Stack, Mask x Field Stack, Position Noise). The value is shown as colour, blue 0 to yellow 1: as dots over the scattering surface (Surface, Paint, Cluster and Area modes; *Surface Samples* up to 20000, evaluated with the code of the stages) and / or on the instances (a dot at every instance; with Display Points Only / Boxes / Spheres the shapes take the colour). Position Noise is shown on the instances only (how far the Noise moved each point, 0 to its Amount). The Mask section and the Noise section have their own *Visualize* menu that does the same without opening the Debugging tab; the Debugging menu wins when both are on. Guide purpose: viewport only, never rendered.

All display and debug guides are in the prim `<output>_View` next to the instancer, because Hydra does not draw the children of a PointInstancer that are not prototypes.

## Stagger Rows cycles (Rows section)
Stagger Rows above 1 now cycles: 1.5 is 0.5, 7.85 is 0.85, a whole number is off (the points line up). In a **Circle** the odd rings are turned about the centre by that fraction of the angle between two neighbours, with their facing, so they stay on their orbit (before, the shift was a straight line along the tangent and the points drifted outward). Line and Curve shift along the path as before.

Evidence: `tests/validate_noise.py` (9 groups, 16 mutations) and `tests/validate_rows.py` (7 groups, new mutations `rows_wrap`, `rows_orbit`). Demos: `dist/Arraytron_v1.24.0_noisetypes_demo.hip`, `_viz_demo.hip`, `_proxy_demo.hip`.
