# Camera optimisation, LOD / proxies and primvars (v0.9.0)

A new **Optimize** tab (the seventh) holds three sections. Everything is reversible and USD-native: instances are **hidden through `invisibleIds`, never deleted**, and level of detail is a switch of `protoIndices` to LOD prototypes. With Camera Optimisation off nothing changes (v0.9.0 reproduces v0.8.0, and the node does not depend on time).

## Camera

Wire a **Camera LOP** into the first input (before Arraytron) and pick it in *Camera Prim* (default `/cameras/camera1`). The camera is read at the current frame, so an animated camera works. It runs as the last stage (the Python LOP `camera_optimize`, after the Bounds Transform), so it sees the final positions, scales and Physics Settle results, and merges with the ids that Grow hides.

| Control | Meaning |
| --- | --- |
| Camera Optimisation | Master switch (off by default). |
| Frustum Culling, Frustum Margin | Hide instances whose bounding sphere is completely outside the camera's view (field of view from the aperture and focal length, clipping range). The margin widens the view by a fraction. The aperture ratio decides the aspect, not the render resolution. |
| Behind Camera, Behind Keep | Keep All, Reduce (keep a stable fraction) or Hide the instances behind the camera. |
| Distance Culling, Max Distance | Hide instances farther than the distance. |
| Density By Distance, Near / Far Distance, Minimum Density | Full density up to Near, falling linearly to the Minimum at Far. Each instance has its own fixed random number keyed on its id, so a nearer camera only ever adds instances back. |
| Seed | Seed of those random numbers. |

An instance is a sphere: its prototype's bounding radius (about the instance origin) times its scale. A read-out shows the visible count and why instances were hidden (frustum, too far, thinned, behind).

## Level of detail and proxies

In the Prototype Bank each row has three optional prim paths: **LOD 1 Prim**, **LOD 2 Prim**, **Proxy Prim** (prims in the stream, like Prim Path). They become extra prototypes of the PointInstancer **after** the hero prototypes (heroes keep their indices). With *Level Of Detail* on, each instance switches to the coarsest level it has passed:

* **Switch By Distance**: LOD 1 / LOD 2 / Proxy distance (camera distance).
* **Switch By Screen Size**: percent of the image height covered by the instance's bounding sphere (below the LOD 1 / LOD 2 / Proxy size).

A level without a prim falls back to the next finer one that is defined; a row without LOD prims keeps its hero. The thresholds need not be sorted (a Proxy distance below the LOD 2 distance skips LOD 2). The switch is one change of `protoIndices`, so a render uses native instancing and the cost is the same as before. An LOD prim must be a different prim from the heroes and from each other (a readable error otherwise).

## LOD generator (v1.8.0)

Instead of modelling LOD and proxy prims by hand, tick **Generate LODs** (Optimize tab, section LOD GENERATOR). Every enabled Prototype Bank row that has no LOD prim of its own for a level gets a reduced copy of its hero, written next to the other prims of the stream (`<Output Prim Path>_LOD/Proto01_LOD1`, `_LOD2`, `_PROXY`) and used as that level. The levels then switch like hand made ones (Camera Optimisation on, Level Of Detail on: by distance or by screen size). The hero prims are never changed, and a prim you type into **LOD 1 Prim**, **LOD 2 Prim** or **Proxy Prim** of a row always wins for that level.

| Control | Meaning |
| --- | --- |
| Generate LODs | Master switch (off by default: nothing is written and the output equals v1.7.0). |
| LOD 1 / LOD 2 / Proxy Triangles (%) | Share of the hero's triangles that level keeps (default 50, 20 and 5). Every mesh of the prototype is reduced by the same share. |
| Minimum Triangles | No generated mesh gets fewer triangles (default 12); a mesh that already has fewer is copied as it is. |
| Generated LODs | Read only: the triangle count of every prototype and of its levels, after the node has cooked. |

**How it reduces.** Vertex clustering on a uniform grid whose cell size is searched until the triangle count meets the target, with the position of every cluster chosen by the quadric error of the surface around it (so a plane stays flat and a sphere stays on the sphere). Collapsed and duplicate triangles are removed; polygons are triangulated. It is plain numpy, so Houdini 22 and 20.5 / 21 give the same result, it is deterministic, and results are cached while the mesh and the settings stay the same (82,000 triangles take well under a second). Carried over: transforms, material bindings, purpose, visibility, and the primvars (uv, colour, ...) with their interpolation (uv are kept per corner of the original triangle). Normals are recomputed smooth.

**Materials (v1.21.0).** The generated levels keep the look of the hero. The **face GeomSubsets** (a material per face group, the usual way to give an object several materials) are carried over: a new triangle belongs to a subset when the original face it came from does (an exact copy keeps the indices), with their family, element type and bindings. The **material binding** of the hero (its own, one inherited from a parent such as an Assign Material on a folder, or a collection binding) is bound directly on every copy, because the copy lives under another parent and would not inherit it. **Material and shader prims are not copied** (a copy loses the connections of the shader network, which rendered the levels black): the levels bind the materials of the hero, so textures, UDIMs and shader changes on the hero reach every level. Before v1.21.0 an object with materials by face group, a material inside the prototype or an inherited binding lost its textures in the LOD levels.

**Limits.** Static meshes only (the first time sample is used); skinned or animated meshes should get hand made levels. Hard edges and sharp features soften at low percentages, which is what the far levels are for. Basic shapes (Cube, Sphere ...) are copied as they are. Checked by `tests/validate_lodgen.py` (8 groups, 5 mutations) with a real icosphere, a quad grid, a thin double sheet, primvars, a material and a camera; how it looks and feels in the viewport is for the user to judge.

Demo: `dist/Arraytron_v1.8.0_lodgen_demo.hip` (render `renders/arraytron_v1.8.0_lodgen_demo_xpu.png`): a ladder of four rocks (hero 5,120 triangles, LOD 1 at 40%, LOD 2 at 12%, Proxy at 3%) and a field of 380 rocks whose level follows the camera distance.


## Primvars

Tick the ones you want in PRIMVARS; the PointInstancer then writes `primvars:<name>` per instance:

| Primvar | Value |
| --- | --- |
| `arraytron_id` | the stable instance id |
| `prototype_id` | the Prototype Bank row of the hero prototype |
| `random` | a stable random number in [0, 1) per id (Primvar Seed) |
| `mask` | the Mask weight (1 without a mask) |
| `density` | the Field Stack weight (1 without a stack) |
| `cluster` | the cluster number (Cluster mode) |
| `arraytron_lod` | the level every instance uses (0 hero, 1 LOD 1, 2 LOD 2, 3 proxy); needs Camera Optimisation |

They can drive shader variation (MaterialX `geompropvalue`), render filtering and downstream tools. Nothing is written unless ticked.

## Demo

`dist/Arraytron_v0.9.0_camera_demo.hip` (render `renders/arraytron_v0.9.0_camera_demo_xpu.png`): 3000 firs on the terrain; the render camera hides what it cannot see and thins the far ones, and the levels are colour coded so they show up: the green hero fir near the camera, an orange cone beyond 8 units, a red proxy cone beyond 10.5. Also a network in `dist/Arraytron_v0.9.0_all_demos.hip`.

## Evidence

`tests/validate_camera.py` (9 groups): the interface (Optimize tab, parameters, bank LOD prims, the camera LOP and PRIMVARS stage, every v0.8.0 parameter unchanged), v0.8.0 reproduced with everything off (no primvars, no hidden ids, **not time dependent**), the frustum / density / screen size / LOD level / merge maths against plain-Python re-implementations, camera culling on the node (frustum with margin, distance, density, behind camera in all three modes, everything at once, reversible) against a frustum built from the camera's own basis vectors and apertures, a rotated camera and an animated camera with frames evaluated out of order, merging with Grow's hidden ids (the radius follows the growing scale), LOD order / distance levels / screen size levels / fallback / duplicate error / reversibility, and every primvar (ids, prototype row, random stable per id and seed, mask and density against independent values, cluster). Eight mutations (`ARRAYTRON_MUTATE=cam_margin|cam_planes|cam_density|cam_lod|cam_merge|cam_screen|cam_fallback|cam_hash`) each fail it. The main (39), physics (19), scatter (24), mask (11), overlap (6), grow (8), paint (16), fields (16), cluster (8) and avoid (7) suites pass on v0.9.0.

## Not verified / limits

How the Optimize tab and the bank's LOD fields look in the parameter pane (GUI). The frustum uses the camera aperture, not the render resolution. The sphere test uses the instance origin and the prototype's bounding radius, not the exact shape. One camera at the current frame (no motion-blur shutter range, no multi-camera union). LOD prims are prims of the stream (not file or SOP rows) and are chosen per bank row. Distance culling and LOD use the camera position at the cook; they do not follow a viewport camera. Mixed LOD of a SOP-geometry prototype works only if its LOD prim is in the stream. USD variant sets and `purpose` are not used (LOD is prototype switching).
