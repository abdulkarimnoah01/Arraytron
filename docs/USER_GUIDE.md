# Arraytron user guide (v1.16.0)

Arraytron is a Solaris (LOPs) node, `arraytron::instancer::1.16.0`, that scatters USD prototypes with a native **UsdGeomPointInstancer**. Every instance has a stable integer id, so you can change the look, the weights, the transform or the selection without reshuffling the layout.

## 1. Quick start (two minutes)

1. Put your scene in LOPs: a reference to your **models** (for example `/World/Props/Rock`) and to a **terrain** (a mesh, `/World/Terrain`).
2. Add an **Arraytron** node and wire the scene into the **first input** (the *Scene Stream*). Extra models can go into inputs 2 to 4.
3. **Source** tab: in the Prototype Bank leave *Source Type* on *Prim Path* and type the model's prim path.
4. **Layout** tab: set *Distribution Mode* to **Surface**, type the terrain in *Surface Prim*, set a *Count*.
5. **Look** tab: switch *Randomize* on for scale and yaw variation.

That is a working scatter. Everything else is optional and stays out of the way until you open its tab.

## 2. The nine tabs

| Tab | What it is for |
| --- | --- |
| **Prototypes** | The Prototype Bank (the models, their weights, scale, LOD / proxy prims), how each point picks a model, the output prim path. |
| **Layout** | Where the points go. Distribution Mode: **Line, Area, Grid, Circle, Curve, Surface, Paint, Cluster, Imported Points**; only the active mode's settings show (**Rows** lay a Line, Circle or Curve out in several rows; **Biome** scatters on a terrain by elevation, slope, moisture and temperature). Then *Move the Layout* (Bounds Transform; a viewport handle moves it too). |
| **Variation** | Per-instance rotation and scale, **Randomize**, the **Mask** (noise, image, mesh primvar) and the **Field Stack** (Height, Slope, Noise, Image, Distance, Exclusion). |
| **Spacing** | **Separation** (Remove Overlapping or Push Apart, with a Priority) and **Avoid Geometry** (keep instances out of a mesh, shape or curve). |
| **Physics** | **Physics Settle**: drop the points into a Bullet simulation, cache the settled result. |
| **Animate** | **Grow**: instances grow or pop up in a sweep across the layout. |
| **Optimize** | **Camera optimisation** (frustum, distance, density, behind-camera), **LOD / proxy** switching, **primvars** for shaders. **Generate LODs** writes reduced copies of the prototypes (`docs/CAMERA_LOD_PRIMVARS.md`). |
| **Debugging** | **Instance overrides** by id (and **Pick Instance**), **debug views**. |
| **Export** | **Export USD** (a self-contained instances file) and what this node stores (the cache read-out). |

## 3. Choosing a distribution

* **Line / Area / Grid / Circle**: regular layouts with a count or spacing. Good for rows, fields, rings.
* **Curve**: points along a curve prim (a road, a fence). The curve is a prim in the Scene Stream, not a separate input.
* **Surface**: points scattered on a mesh by count or density, with slope limits and normal alignment.
* **Paint**: points you paint with the viewport brush (section 6).
* **Cluster**: groups of instances around centres on a surface (flower patches, rock piles).
* **Imported Points**: put the instances on the points of an FX simulation or any other points, from a SOP or a USD Points / PointInstancer prim; the instances follow the simulation, and you control the prototype percentages (Selection Mode *Even Percent*), scale, rotation and the ids for AOVs. See `docs/IMPORTED_POINTS.md`.

Every mode produces points with the same attributes, so every later stage works on all of them.

## 4. Shaping the result (Look and Spacing)

Think of it as a pipeline, in this order: generate points, **Mask**, **Field Stack**, **Variation**, **prototype selection**, **Separation / Avoid Geometry**, **Physics Settle**, **overrides**, **Grow**, then (as USD stages) **camera optimisation** and **debug**.

* **Field Stack** rows are 0 to 1 values combined with Multiply / Add / Subtract / Min / Max. The classic recipe: Slope (gentle ground) x Distance to a road curve (clear road) x Noise (patchy) x Exclusion of a pond. *Density* removes points by the combined weight; *Scale* shrinks them.
* **Separation** keeps instances from overlapping (each is a bounding sphere). *Priority* decides who survives: Id Order, Biggest First, Smallest First, Random.
* **Avoid Geometry** pushes instances out of (or removes them from) a prim you pick.

## 5. Stable ids

Every point gets a deterministic integer id. Changing rotation, scale, selection weights, masks or materials never renames a point; a density mask or a Remove only ever removes ids; adding points (a higher count, more clusters, more paint) never moves the earlier ones. Ids are what overrides, paint edits, caches and downstream FX hang on. They are written as `ids` on the PointInstancer and can be exposed as the primvar `arraytron_id`.

## 6. Painting (Layout tab, Mode = Paint)

Press **Start Painting** (or select the node and press Enter in the viewport). Drag over the **Paint Target** to paint. The prompt line at the top of the viewport shows the live brush values; the brush ring is **orange** for Add, **red** for Remove, **blue** for Replace and **green** for Relax, and a white inner ring shows a strength below 1.

| Mouse | |
| --- | --- |
| LMB drag / click | paint (a click paints one dab) |
| Ctrl + LMB | erase |
| Shift + LMB | relax (spread the points evenly) |
| Ctrl + Shift + LMB, drag sideways | brush radius (150 pixels = double) |
| Wheel + Shift | radius |
| Wheel + Ctrl | strength |
| Wheel + Ctrl + Shift | density |
| Alt, middle mouse | camera navigation, as always |

| Keys | |
| --- | --- |
| `[` `]` | radius smaller / larger |
| `-` `=` | strength lower / higher |
| `,` `.` | density lower / higher |
| `1` `2` `3` `4` | Add, Remove, Replace, Relax |
| `F` | next falloff (Linear, Smooth, Gaussian, Hard) |
| `H` | hide / show the shortcut help line |
| Esc, Enter | finish |

The values live in the node's parameters (Brush Radius, Strength, Density, Operation, Falloff), so every shortcut also moves the sliders. Painted points are stored in the node and keep their ids. See `docs/PAINT_BRUSH.md`.

## 7. Overrides (Export tab)

To fix one instance by hand add a row to **Instance Overrides**: give the **Instance Id** (the easy way: press **Pick Instance in Viewport** and click the instance; Ctrl+click also ticks Delete, Esc finishes. Or read the *Arraytron Id* primvars or the *Id* debug colours), then tick **Delete**, or set **Move**, **Rotate**, **Scale** or **Prototype Row**. Overrides are applied last (after the physics, before Grow), keep working when other settings change, and removing the rows brings the generated instances back. Python: `hou.pwd().hdaModule().override_set(node, id, move=(0,1,0))`, `override_delete_ids(node, [ids])`, `override_clear(node)`.

## 8. Debug views (Finish tab)

Switch **Debug Views** on to see inside the result: the *Generated Points* (white), the *Rejected Points* (red: masked, thinned, separated or avoided), the final points coloured by *Prototype*, *Id* or *Weight*, the *Axes* of every instance, the *Collision Radius*, the *Cluster Centres*. They are guide-purpose prims under `<output>/Debug`: visible in the viewport, never rendered.

## 9. Camera, LOD and primvars (Optimize tab)

Wire a Camera LOP before Arraytron and pick it. **Frustum**, **distance** and **density** culling and **behind-camera** reduction hide instances through `invisibleIds` (nothing is deleted; switch it off and they come back). Give a Prototype Bank row a **LOD 1 / LOD 2 / Proxy** prim and **Level Of Detail** switches instances by distance or screen size. Tick **primvars** (`arraytron_id`, `prototype_id`, `random`, `mask`, `density`, `cluster`, `arraytron_lod`) to drive shaders. See `docs/CAMERA_LOD_PRIMVARS.md`.

## 10. Output and export

The node outputs one PointInstancer at the *Output Prim Path* (default `/World/Arraytron`) with its prototypes under `/Prototypes`. **Export USD** (Export tab) writes that result, self-contained, to a file for caching or hand-over (`docs/CACHING_AND_PIPELINE.md`).

## 11. Where to go next

`docs/INDEX.md` lists every document. Problems: `docs/TROUBLESHOOTING.md`.
