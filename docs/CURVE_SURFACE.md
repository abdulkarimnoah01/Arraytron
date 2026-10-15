# Curve (v0.4.5) and Surface Scatter (v0.4.6)

Two new **Distribution Mode** entries that read geometry from the incoming Solaris stage. Both follow the usual pipeline (Randomize, Prototype Bank, Bounds Transform, Physics Settle) and both reuse the `p@align` hook of Circle Facing: the alignment is composed last, so Instance Transform, Randomize and the Prototype Bank rotation offset apply to the prototype first.

How the HDA reads stage geometry (the open question from the master plan, decision 3): with **pxr on the stage of the Source Resolver**, from a prim path picked in the parameter. No second input and no SOP path; anything an artist wants to use (a SOP curve, a scan) can be brought into the stream with a SOP Create LOP. The prims are used at their **world transform**, so points land where the geometry is drawn; leave the Bounds Transform at its defaults to keep them there.

## Curve (v0.4.5)

| Control | Meaning |
| --- | --- |
| Curve Prim | A BasisCurves prim, or any prim whose subtree holds BasisCurves: linear, or cubic with a bezier, bspline or catmullRom basis, nonperiodic, periodic or pinned. NurbsCurves and HermiteCurves are refused with a clear error. |
| Curve Index | -1 uses every curve found (stage traversal order, then storage order inside a prim); 0, 1, ... one curve. |
| Placement | **By Count**: Count points on each curve, evenly by arc length, both ends included (a closed curve does not repeat its start; Count 1 sits at the start). **By Spacing**: a point every Spacing units, floor(Length / Spacing) + 1 on an open curve (Spacing is clamped to 0.001). **Random**: Count points per curve at arc lengths keyed on the stable id and Seed, so raising Count never moves earlier points. At most 10000 points in total. Ids run through the curves in order. |
| Reverse | Walks each curve from its end; ids and tangents flip. |
| Alignment, Up, Up Vector, Roll | Tangent turns each instance so +Z follows the curve and +Y stays as close as possible to World Y (or a custom Up Vector; a curve running along it picks a stable side axis); Roll turns about the tangent. None keeps the prototype orientation. |

Cubic curves are tessellated at 64 steps per segment and resampled by arc length, so a bezier's points lie within 0.001 of the analytic curve in the tests. A pinned bspline repeats its end points twice and a pinned catmullRom once so the curve starts and ends on its first and last control point; that is the standard end padding, not checked against another implementation. The guide shows the tessellated curve.

## Surface Scatter (v0.4.6)

| Control | Meaning |
| --- | --- |
| Surface Prim | A Mesh, a Cube / Sphere / Cylinder / Cone / Capsule prim (tessellated at 24 segments), or any prim whose subtree holds some. The output prim itself is skipped. |
| Amount, Count, Density | By Count: exactly Count points. By Density: Density points per unit of world-space area of the whole surface (all triangles, before the slope limits). At most 10000. |
| Seed | Point i depends only on its id and the seed (area-weighted triangle by CDF, then a uniform barycentric draw), so raising Count adds points and never moves earlier ones, as long as the surface and the slope limits stay the same. |
| Normal | Face (flat, exact) or Smooth (area-weighted vertex normals blended across the triangle; on meshes with split points the vertex normals are per face, i.e. faceted). Authored `normals` are not used. |
| Align to Normal | 0 upright, 1 the up axis (+Y) on the normal, in between a normalized blend (exact for 0 and 1; the angle is exactly half at 0.5). Applied after Randomize, so **Yaw Only turns the instances about the surface normal**. |
| Offset | Moves points along the normal (negative sinks them). |
| Slope Min / Max (deg) | Slope = angle between the triangle normal and world up. Triangles outside the range are removed from the draw, so the count stays exact; downward faces count as 90 to 180, which the default Max of 90 excludes. If nothing is left there are no points and a node warning says why. |

Orientation follows the stage: leftHanded meshes and negative scales are corrected so the drawn normal wins. The guide draws the bounding box of the surface.

## Evidence

`tests/validate_scatter.py v0.4.6` passes 24 groups (`tests/validation_scatter_v0.4.6.json`; v0.4.5 passes its 11 curve groups): every Surface point is compared with an independent plain-Python implementation of the triangle and barycentric draw, curve points are hand-derived on an L and checked against analytic beziers, orientations are read back as instance matrices (tangent, up, Roll, Custom Up, normal alignment on a 30 degree plane, ceilings, leftHanded and mirrored meshes, sphere / cube / cylinder / capsule / cone normals), plus errors, caps, stability, Bounds Transform, Physics Settle as the spawn, and bit-for-bit equality of the older modes with the previous release. 8 deliberate breakages (`ARRAYTRON_MUTATE=curve_arclength|curve_tangent|curve_bezier|curve_random|surface_area|surface_normal|surface_slope|surface_offset`) each make it fail; the first run of `curve_random` passed until an exact hash check was added. The main suite (39 groups) and the physics suite (19) also pass on v0.4.6. Karma XPU renders: `renders/arraytron_v0.4.5_demo_xpu.png` (crates and barrels along an S bend, tangent aligned) and `renders/arraytron_v0.4.6_scatter_demo_xpu.png` (rocks on the gentle ground, crates square on the steep slopes).

Found on the way: the implicit-shape tessellation in `shape_mesh` (Sphere, Cylinder, Cone, Capsule) had **inward** normals (the cube was right); fixed in v0.4.6. The Physics Settle colliders use the same meshes as triangle meshes, and its suite still passes.

## Limits

* Surface points are **not relaxed**: neighbours can overlap (minimum distance and relaxation are the master plan's v0.8). No attribute, texture or noise masks (v0.5).
* Smooth normals use only the mesh topology; no subdivision limit surface; instance proxies and nested point instancers are ignored.
* Curve and surface geometry is read at the default time (no animated curves or meshes).
* GUI items not yet checked by a person: the Curve and Surface folders (hide/disable behaviour, prim pickers) and the guide curves in the viewport.
