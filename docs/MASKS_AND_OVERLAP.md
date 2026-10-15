# Masks (v0.5.0) and No Overlap (v0.5.1)

## Masks

A **mask** is one number from 0 to 1 for every generated point: "how much do I want something here?". Arraytron takes that number from noise, from an image, or from a value painted on a mesh, and uses it to **thin out** the points (Density), to **scale** them, or both. It works with every Distribution Mode (Line, Area, Grid, Circle, Curve, Surface) and sits right after the generator, before Randomize and the Prototype Bank.

| Control | Meaning |
| --- | --- |
| Mask Source | None (nothing changes: the output is bit-for-bit the previous release), **Noise**, **Image**, **Mesh Primvar**. |
| Mask Effect | **Density**: a point survives with a probability equal to its weight (1 always, 0 never). Every point has its own fixed random number keyed on its id, so *raising a weight only ever adds points*, and the survivors keep their ids and positions. **Scale**: nothing is removed; scale = Min Scale at weight 0 up to 1 at weight 1 (multiplied in after Randomize and the Prototype Bank scale). **Density + Scale**: both. |
| Invert, Low, High | Invert uses 1 - mask. Low and High are the contrast control: values at or below Low give weight 0, at or above High weight 1, linear in between. |
| Mask Seed | Seed of the noise and of the per-point random numbers. |
| Noise: Frequency, Offset, Octaves, Roughness, Contrast | Fractal value noise of the point position (features per scene unit). Fractal noise clusters around 0.5, so Contrast (default 2.5) stretches it around 0.5 before Low / High. |
| Image: Image, Channel, Projection, Image Center / Size, Outside The Image | The image is read with OpenImageIO, **values as stored** (no colour transform; a black to white 8-bit map gives 0 to 1) and sampled bilinearly. **Top (XZ)**: laid over the XZ plane seen from above, X to the right, the image top is -Z. **Front (XY)**: the image top is +Y. **Mesh UV**: read through the `st` primvar (the UV Primvar name) of the Mask Prim mesh. Outside the image: Black (0), Repeat or Clamp. |
| Mesh Primvar: Mask Prim, Primvar, Outside The Mesh | A float primvar of the meshes under the Mask Prim (vertex, faceVarying, uniform or constant interpolation), interpolated across the triangles. The point is **looked up from above**: the highest triangle under its (X, Z) wins, so it suits terrain-like meshes; a point not above any triangle gets the Outside value. |

The mask is read at the position of each point **in the space the points are generated in (before the Bounds Transform and before Randomize's Position jitter)**. For Surface Scatter and Curve that is world space, so leave the Bounds Transform at its defaults to keep the mask where you painted it.

Because points can now be removed, ids are no longer always 0..n-1. The USD ids stay stable. Sequential prototype selection now follows the **point order** (which equals id order without a mask), and Cycle still follows the id, so a survivor keeps its prototype.

## No Overlap

Keeps instances from sitting on top of each other. Every instance is treated as a **bounding sphere**: the sphere of its prototype (from the real prototype geometry, placed with the instance's position, orientation and scale) or a Fixed Radius at the instance scale. Two instances overlap when their centres are closer than **Spacing x (r1 + r2)**.

| Control | Meaning |
| --- | --- |
| No Overlap | **Off**; **Remove Overlapping**: points are visited in id order and a point is deleted when an earlier surviving point overlaps it (the first points always survive, survivors keep their ids and positions, adding points at the end never changes earlier survivors); **Push Apart**: every point stays and overlapping pairs are moved apart along the line between them, pass after pass. |
| Size From, Radius | Prototype Bounds (default) or a Fixed Radius. |
| Spacing | The tweakable part: 1 means the bounding spheres just touch, 0.7 lets them sink into each other by 30%, 1.5 leaves a gap of half a radius. |
| Measure In | XZ (ground plane) ignores height; XYZ is the true 3D distance (default). |
| Iterations, Strength | Push Apart only: passes (default 30) and the fraction of each pair's overlap corrected per pass (default 0.5, stable). |

It runs **after** Randomize and the Prototype Bank, so the actual sizes and jittered positions decide what overlaps, and **before** Physics Settle (the spawn it receives is already thinned). Push Apart in a crowded area may leave some overlap; the read-out under the controls says how much ("the worst overlap left is x% of the required distance"). Push Apart moves points off a curve or surface, so on Curve and Surface use Remove Overlapping (a node warning says so). This is not a physics solver: it ignores the real shape, only the bounding sphere (for a detailed non-overlapping pile use Physics Settle).

## Evidence

`tests/validate_mask.py` (11 groups) reads results from the USD stage with images and meshes whose answer is known exactly: a checkerboard sampled at pixel centres keeps exactly the white pixels (Top and Front, Invert, shifted centre), channels, Outside modes, a ramp image gives exact Scale values through Low / High / Invert / Min Scale, vertex / faceVarying / uniform / constant primvars on a tilted plane, UVs, errors, and noise decisions are compared with an independent plain-Python implementation. 6 mutations (`ARRAYTRON_MUTATE=mask_flip|mask_high|mask_v|mask_density|mask_scale|mask_noise`) each make it fail. `tests/validate_overlap.py` (6 groups): the survivors of Remove Overlapping equal an independent greedy on the plain layout, no two survivors overlap (brute force over all pairs), every removed point does overlap an earlier kept one, XZ against XYZ on stacked grids, per-prototype radii, and Push Apart leaves no overlap when feasible, never moves a point that overlaps nothing, reports a residual that matches the output, and separates coincident points. 5 mutations (`overlap_order|overlap_tol|overlap_scale|overlap_axes|push_sign`) each fail the suite. Older modes are bit-identical to the previous release in both suites, and the main (39), physics (19) and scatter (24) suites pass on v0.5.1. Karma XPU renders: `renders/arraytron_v0.5.0_mask_demo_xpu.png` (noise patches of rocks, a blob-image crowd of crates) and `renders/arraytron_v0.5.1_overlap_demo_xpu.png` (as generated | Remove | Push Apart).

## Limits

* The mask is a point filter, not a painted brush: painting is v0.6. SOP attribute and texture-node sources are not offered; bring a SOP attribute in as a USD primvar on a mesh.
* Mesh Primvar and Mesh UV look from above (one height per XZ); a mesh with overhangs uses the highest surface.
* Image is read once per file change (the cache key is the file time). Only the first frame of an image is used.
* No Overlap uses bounding spheres: a long thin prototype counts as a big sphere. Push Apart is not exact in crowded areas and does not keep points inside an Area rectangle.
* GUI items not yet checked by a person: the Mask and No Overlap folders (conditionals, file chooser and prim picker).
