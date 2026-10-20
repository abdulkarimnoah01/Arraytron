# Field Stack (v0.7.0)

A Field Stack is an ordered list of **fields**. Each field gives every point a number from 0 to 1; the rows are combined into one weight per point, and that weight removes points (Density), shrinks them (Scale), or both. It works on every Distribution Mode (Line, Area, Grid, Circle, Curve, Surface, Paint) and sits in the **Variation** tab under FIELD STACK, after the Mask. The older Mask is untouched and still works; when both are used their scales multiply.

## The fields

| Field | Value is 1 when ... | Settings |
| --- | --- | --- |
| **Height** | the point's Y is between Min and Max | Min Height, Max Height, Falloff (distance over which the value fades to 0; 0 = hard edge) |
| **Slope** | the surface under the point has a slope between Min and Max degrees | Prim (the surface judged, read from above), Min / Max Slope, Falloff. A point that is not above the prim is not judged (value 1) |
| **Noise** | the fractal noise at the point is high | Frequency, Offset, Octaves, Roughness, Contrast, Noise Seed (the same noise as the Mask) |
| **Image** | the image channel under the point is bright | Image, Channel, Projection (Top XZ / Front XY), Center, Size, Outside |
| **Distance** | the point is far enough from the Prim (a mesh, shape or curve, e.g. a road) | Prim, Near Distance (0 at or below), Far Distance (1 at or above), Measure In (XZ ignores height, XYZ) |
| **Exclusion** | the point is outside a closed mesh or shape and farther than the margin | Prim (closed), Margin, Falloff |

Every row also has **Enable**, **Combine** and **Invert** (use 1 - value).

## Combining

Rows run top to bottom. The first enabled row sets the running value (its Combine is ignored); each next row is joined with its **Combine**: Multiply (both must be high), Add, Subtract (running - value), Min, Max. The running value is clamped to 0..1 after every row. The classic "density x slope x noise x road x pond" is every row on Multiply.

## Effect

* **Density**: a point survives when the weight is greater than its own random number, which is keyed on its id and the Stack Seed. A higher weight therefore only ever adds points, and the survivors keep their ids and positions.
* **Scale**: the instance is scaled between Min Scale (weight 0) and 1 (weight 1). It multiplies the Mask Scale if the Mask also scales.
* **Density + Scale**: both.

A read-out under the stack says how many fields are active, the weight range and how many points survived.

## Where the points are measured

Heights, positions and images use the space the points are generated in (like the Mask and Grow), and prims are read at their world transform. So with a Bounds Transform away from identity, point positions and prims no longer line up; keep it at the identity (or use world-space layouts such as Surface and Paint) when the fields use prims.

## How it is built

`src/arraytron_fields.py` in the PythonModule; the Python SOP `FIELD_STACK` sits between `MASK_PROCESSOR` and `VARIATION_PROCESSOR` (so everything later, including No Overlap, Physics Settle and Grow, sees the thinned points). The rows are a multiparm (`fields`, default 0 rows: an empty stack changes nothing, and v0.7.0 reproduces v0.6.0 exactly). Point-to-triangle distances are exact and use an XZ grid so that only triangles within the far distance are tested; inside / outside for Exclusion counts the surface crossings along +Y (so the mesh must be closed). Curves are measured as polylines.

## Demo

`dist/Arraytron_v0.7.0_fields_demo.hip` (render `renders/arraytron_v0.7.0_fields_demo_xpu.png`): 1600 surface points on the terrain thinned to 366 by four rows, all Multiply: Slope (gentle ground only), Distance to the S-curve road, Noise (patchy groves) and Exclusion of a pond sphere. It is also one of the networks in `dist/Arraytron_v0.7.0_all_demos.hip`.

## Evidence

`tests/validate_fields.py` (16 groups): the interface and stage order, every v0.6.0 parameter unchanged, modes 0 to 5 identical to v0.6.0, empty and all-off stacks neutral; band, ramp and Combine against plain Python; point-to-triangle and segment distances against dense sampling and the grid search against brute force (XZ and XYZ); the inside test and Exclusion against the analytic box; every field type through the real node against independent formulas (Height, Slope with flat and 45 degree ground, noise equal to the Mask noise, an image gradient read back, Distance to a curve and to a mesh, Exclusion with margin and falloff); all five Combine operations, the ignored first Combine, disabled rows and chained rows; Density against an own splitmix64 per-id random number, Scale, Density + Scale, Stack Seed, the read-out; monotonic behaviour (a higher weight only adds points); the stack on Surface Scatter; readable errors. Eight mutations (`ARRAYTRON_MUTATE=field_height|field_slope|field_op|field_order|field_dist|field_inside|field_smooth|field_density`) each fail it. The main (39), physics (19), scatter (24), mask (11), overlap (6), grow (8) and paint (16) suites pass on v0.7.0.

## Not verified / limits

How the new Look-tab section looks in the parameter pane (not seen in the GUI). Slope uses the face normal of the triangle under the point (not smoothed). A mesh used for Exclusion must be closed (an open mesh gives wrong inside answers; Distance still works). The Distance field on very dense meshes tests only triangles within the far distance but builds its grid in Python (about a second for 100,000 triangles). No Overlap runs after the stack, not before. Curvature, normal-direction and painted-mask fields are not in this version (the painted points of v0.6 are a distribution, not a field).
