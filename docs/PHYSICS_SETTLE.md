# Physics Settle (Arraytron v0.4.0)

An optional system that lets a distribution *fall into place*: the points of any Line, Area, Grid or Circle distribution become rigid stones, Houdini's native Bullet solver (the `rbdbulletsolver` SOP) runs inside the HDA, and the settled positions and orientations replace the spawn state in the normal USD PointInstancer. It was built for the look of loose gravel (railway ballast): small stones resting against and on top of one another.

Off by default. With **Physics Settle** off the output is bit-for-bit the v0.3.6 output (every array of every mode, tested against the real v0.3.6 HDA), and none of the physics nodes cook.

## Workflow

1. Build the distribution as usual. For a bed of stones use **Area**: *Size* is the spawn region, *Count* is the number of stones, **Randomize** (rotation 180 on all axes, a scale range) and the **Prototype Bank** give the variety. Nothing is duplicated in the Physics folder.
2. Turn **Physics Settle** on. The stones now show their *spawn state*: lifted by **Drop Height** and stacked so that no two overlap. The viewport shows two extra guide outlines: **Drop** (the spawn bounds lifted by Drop Height) and **Ground** (the ground plane at Ground Height). The **Spawn** read-out says how many stones come from which distribution and the height range of the spawn.
3. Press **Simulate & Cache**. A progress dialog (with Cancel) runs the simulation frame by frame; it stops as soon as the pile is at rest. The last frame is written to the cache folder.
4. The settled pile now feeds the PointInstancer. Changing any setting keeps the old pile on screen marked **STALE** (status line, node warning, `arraytron:physics` state `stale` on the instancer prim) until you simulate again; changing the setting back makes it settled again without simulating. A change of the number of stones cannot reuse the old result and shows the spawn state ("Not simulated").

## Controls

| Control | Default | Meaning |
| --- | --- | --- |
| Physics Settle | off | The master switch. |
| Status, Spawn | - | Read only. Status: settled / STALE / not simulated, frames simulated, how many stones were still moving, the largest movement in the last half second. Spawn: stone count and region, spawn height range, a warning above 2000 stones. |
| Simulate & Cache, Clear Cache | - | Run and freeze the simulation; delete this node's cache files. |
| Drop Height | 0.3 | Height of the lowest spawn layer above the distribution plane (the distribution's own height, so Position jitter in Y adds to it). |
| Avoid Overlap At Spawn | on | Lifts every stone that would overlap an earlier one (bounding spheres, stable pseudo-random order) just clear of it, so the solver never starts interpenetrating. Off: all stones start at the drop height, only safe for sparse spawns. |
| Seed | 1 | Order of the stacking, i.e. which stones end up on top. Positions, rotations and scales still come from Randomize and the Distribution seeds. |
| Gravity | 9.80665 | Scene units per second squared along -Y. The scene is assumed to be in meters. |
| Density | 2600 | kg/m3. It matters only between differently sized stones. |
| Friction | 0.9 | Combined friction (ground and colliders are fixed at 1). Low values slide, 0.9 interlocks like gravel. |
| Bounce | 0.1 | Restitution; gravel is dead. |
| Air Drag | 5 | Quadratic drag: the fall speed levels off at about sqrt(Gravity / Air Drag), 1.4 m/s at the default (measured within 2%; 0 is a vacuum). This is the control that turns a scattering pour into a tight pile; it also makes the fall cheaper to simulate. |
| Maximum Sim Time | 10 s | Longest simulation at the scene frame rate. It stops earlier at rest. |
| Collision Quality | Standard | Draft, Standard, High: proxy hull vertex cap (24 / 96 / 256), collision margin (4% / 1.5% / 0.6% of the thinnest stone), substeps and solver iterations (see the table below). |
| Ground Plane, Ground Height | on, 0 | An infinite static plane. |
| Collider Prims | - | Space separated prim path patterns (`*` wildcards) of meshes or cube/sphere/cylinder/cone/capsule prims in the incoming stream, e.g. `/World/Track`. They collide as static triangle meshes at their world transform (a concave mesh is fine). The output prim and the prototypes should not match. |
| Error If Not Simulated | off | Makes a missing or stale cache a node *error* instead of a warning. Turn it on for farm and hand-off scenes. |
| Cache Folder | `$HIP/arraytron_cache` | Where the frozen results live. It is not inside the HIP: ship it with the scene. |

## What it does inside the HDA

```
... > PROTOTYPE_ASSIGNMENT --------------------------------------------+> PHYSICS_SWITCH > OUT_POINTS      (Physics Settle off)
                      \                                                |
                       > PHYSICS_WORLD > PHYSICS_SPAWN > PHYSICS_APPLY +                                     (on)
                                              \
                                               > PHYSICS_PROXIES > PHYSICS_SOLVER <  PHYSICS_COLLIDERS      (only cooks while simulating)
```

* **PHYSICS_WORLD** (VEX): applies the Bounds Transform (scale was already applied about the pivot, then rotation about the pivot, then position) to the points and their orientations, because the simulation has to happen in world space to meet world-space colliders and the ground. The PointInstancer prim's own transform stays identity while physics is on, and the Bounds guide applies the same transform. Scale Instances is ignored: a stretched rigid body makes no sense, scale only moves stones apart.
* **PHYSICS_SPAWN** (Python): Drop Height and the overlap-free stacking.
* **PHYSICS_PROXIES** (Python): one packed convex proxy per stone. The proxy is the convex hull of the real prototype geometry (every mesh, or cube/sphere/cylinder/cone/capsule prim, under the prototype prim) in the prototype's own frame, so its root transform and an off-centre pivot are respected exactly as the instancer applies them; the stone's own scale (uniform or not, including the per-prototype scale) is baked into its hull.
* **PHYSICS_SOLVER**: the Bullet SOP solver. Margin, substeps and iterations come from the quality preset and the stones' size: the margin is a few percent of the thinnest stone (Houdini's default of 2 cm is bigger than a gravel stone), and the substeps keep a stone from moving more than 30% of its thinnest size per substep at the fastest expected speed (many while the stones fall, fewer once the pile only shuffles).
* **Simulate & Cache** (`hdaModule().bake`): steps the solver with `geometryAtFrame` (the playhead is not touched), watches the rest test, and writes id, position and orientation of the last frame to `<Cache Folder>/<node>_<fingerprint>.bgeo.sc`.
* **PHYSICS_APPLY** (Python): reads the cache with the matching fingerprint (or the newest older one, as STALE) and replaces position and orientation by id. Ids, scales and prototype indices are never touched.

The fingerprint is a hash of the spawn state, the proxy hulls, the collider triangles and every setting that changes the simulation, so a result is only called settled when it really belongs to the current state.

The state is also written to the stage: the PointInstancer prim carries `customData["arraytron:physics"]` with `state` (`settled`, `stale`, `missing`), `frames`, `atRest`, `stones` and the cache `key`, so a pipeline check can refuse an unsettled pile without opening Houdini.

## What "at rest" means

Stones never stop exactly: Bullet keeps a few resting stones creeping or rocking (its sleeping thresholds have no effect in Houdini's SOP solver, measured). The simulation therefore stops when, on 3 consecutive checks (6 frames apart), at most **2% of the stones** (a stone counts as moving if, over the last half second, it moved more than **8% of the median stone size** or turned more than **0.15 rad**). That is a practical tolerance, not a guarantee: at 1000 stones up to 20 stones may still be creeping. The status shows the count and the largest remaining movement. If **Maximum Sim Time** runs out first, the cache is still written and the status says "NOT at rest: N stone(s) were still moving", `atRest` is false on the stage, and you can raise the time or the quality and simulate again. A tighter tolerance (1% with 4 checks) was tried and a 160-stone pile did not satisfy it within 10 s, because 3 to 5 stones keep creeping for a long time.

## Accuracy and performance

All numbers are measured in Houdini 22.0.368 on this machine by `tests/bench_physics.py` and `tests/validate_physics.py` from the USD stage that Karma renders: the instance matrices are read back with `ComputeInstanceTransformsAtTime`, the stone meshes are re-read from the prototype prims and re-hulled with an independent numpy quickhull, and pair penetration is measured with a separating-axis test (exact for overlap). The stones are 27 mm thick at the thinnest.

Piles of identical stones dropped from a spawn that grows with the count (Area side 0.3 m x sqrt(count/160)), Standard unless noted, time limit 20 s of simulation, Times are wall-clock for the whole Simulate & Cache and vary by about 30% from run to run. "Pair penetration" is the worst overlap of any two real stone meshes (and its size relative to the thinnest dimension); "floating" counts stones with no chain of contacts to the ground.

| stone | stones | quality | proxy vertices | seconds | frames | at rest | still moving | pair penetration | ground penetration | floating | on top of others |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 17-vertex mesh | 50 | Standard | 17 | 2.2 | 210 | True | 0 | 0.22 mm (0.8%) | 0.21 mm | 0 | 0 |
| 17-vertex mesh | 100 | Standard | 17 | 2.6 | 162 | True | 1 | 0.39 mm (1.4%) | 0.14 mm | 0 | 11 |
| 17-vertex mesh | 200 | Standard | 17 | 6.2 | 180 | True | 2 | 0.37 mm (1.4%) | 0.36 mm | 0 | 38 |
| 17-vertex mesh | 400 | Standard | 17 | 14.4 | 186 | True | 4 | 0.40 mm (1.5%) | 0.20 mm | 0 | 123 |
| 17-vertex mesh | 800 | Standard | 17 | 32.3 | 198 | True | 12 | 0.43 mm (1.6%) | 0.20 mm | 0 | 318 |
| 17-vertex mesh | 200 | Draft | 17 | 5.2 | 378 | True | 1 | 0.83 mm (3.0%) | 0.96 mm | 0 | 4 |
| 17-vertex mesh | 200 | Standard | 17 | 6.2 | 180 | True | 2 | 0.37 mm (1.4%) | 0.36 mm | 0 | 38 |
| 17-vertex mesh | 200 | High | 17 | 17.2 | 240 | True | 1 | 0.32 mm (1.2%) | 0.11 mm | 0 | 46 |
| 90-vertex mesh | 200 | Draft | 24 | 6.5 | 444 | True | 3 | 6.29 mm (22.7%) | 4.11 mm | 0 | 18 |
| 90-vertex mesh | 200 | Standard | 90 | 30.8 | 474 | True | 3 | 0.26 mm (0.9%) | 0.13 mm | 0 | 43 |
| 90-vertex mesh | 200 | High | 90 | 61.0 | 468 | True | 4 | 0.27 mm (0.9%) | 0.05 mm | 0 | 43 |

What this says:

* **Accuracy is set by the collision margin and by how well the proxy matches the mesh.** For the 17-vertex stone the proxy is the exact hull, so the penetration is just the margin (Standard 0.4 mm, about 1.5% of the 27 mm thickness); Draft's 4% margin shows as 0.8 mm, High's 0.6% as 0.3 mm. No stone floats and none sinks through the ground or a collider.
* **The hull vertex cap is the real quality knob for detailed stones.** A 90-vertex stone with Draft (24-vertex proxy) overlaps its neighbours by 6 mm (23% of its thickness): visible intersections. Standard (cap 96) uses the whole hull and is as accurate as High (0.26 mm) but takes half the time; High (cap 256, margin 0.6%, twice the substeps and iterations) buys almost nothing more here and costs 2x. Use **Draft only to block a pile out**, **Standard for finals**, **High** when a detailed stone needs the tightest contacts.
* **Draft is cheaper per frame but not cheaper overall on small stones**: its coarse substeps and wide margin let the pile creep for twice as many frames (378 against 180), so the wall-clock is about the same; it wins when the hull is large (24 against 90 vertices: 6.5 s against 31 s).
* **Cost is roughly linear in the stone count in this range** (50 to 800 stones: x16 stones took x15 time, and the pile stays at 180 to 210 frames because every pile is simulated only until at most 2% of the stones are still moving). The substep count also grows with the fall height, so a tall spawn column costs more per frame. Cheap levers, in order: keep the spawn compact (a smaller Area and Drop Height), keep Air Drag on, lower Maximum Sim Time, use Draft to block out, Standard for the final.
* **Hull proxies approximate the real mesh.** Convex stones (gravel) are exact up to the margin. A strongly concave prototype rests on its hull (it will look like it floats on its concave side); split such a prototype into convex parts or accept the gap.
* **Determinism.** Two bakes of the same scene give the identical result (tested), so the cache can be regenerated on another machine with the same Houdini version; across versions Bullet may differ slightly, which is why the cache file, not the simulation, is what to ship.

## Limits

* Static: one frozen pile per node. No animated colliders, no animation of the settings, no simulation over the timeline.
* Convex hull proxies, mesh and basic-shape (cube, sphere, cylinder, cone, capsule) prototypes and colliders only; point-instancer prototypes inside the prototype are ignored. Implicit shapes are tessellated at 24 segments.
* Prototype and collider geometry changes are part of the fingerprint, so any edit of either asks for a new simulation.
* All stones share one density, friction and bounce.
* Moving or rotating the finished pile: it is simulated in world space, so changing the Bounds Transform asks for a new simulation; to move a finished pile without simulating, place the output prim with an Xform LOP downstream.
* The Cache Folder is outside the HIP. Without it the node shows the spawn state with a warning (or an error with Error If Not Simulated).
* GUI items not yet checked by a person: the parameter layout, the greyed-out state while off, the Simulate & Cache button with its progress dialog (the dialog exists only in the interactive app), and the Ground and Drop guide curves in the viewport.
