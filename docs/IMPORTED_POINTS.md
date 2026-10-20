# Imported Points: scatter on FX simulation points and any other points (v1.5.0)

Distribution Mode **Imported Points** (Layout tab, mode 9 in the list) puts the instances on points that come from somewhere else: a **SOP network** (a POP, Vellum, FLIP or Pyro simulation, a scatter, a point cloud, a Houdini cache ...) or a **USD Points / PointInstancer prim** of the Scene Stream (an FX cache imported as USD). Everything after the distribution works on them like on any other mode, so the artist keeps full control: prototype percentages, scale, rotation, ids for AOVs, Variation, Mask, Field Stack, Separation, Avoid Geometry, Physics, overrides, Grow, camera optimisation, LOD and primvars. It works in Houdini 22 and in Houdini 20.5 / 21 (same parameters, same USD).

## Quick start

1. Layout tab: Distribution Mode **Imported Points**.
2. *Source*: **SOP Node** and pick the SOP (for example `/obj/sim/OUT_POINTS`), or **USD Prim** and type the prim path of a Points / PointInstancer in the stream.
3. Source tab: add your prototypes. *Selection Mode* **Even Percent** and the *Weight* of each row set the percentages (the **Share Of The Points** read-out shows them).
4. *Scale*: **From Attribute** (`pscale`) times the multiplier. *Orientation*: **Along Velocity**.
5. The instances follow the simulation over the timeline.

## Where the points come from

| Source | What is read |
| --- | --- |
| **SOP Node** | The points of the SOP at the current frame (an Object Merge inside the node). Every float and integer point attribute is available by name. The points are used as stored (no object transform). |
| **USD Prim: Points** | `points`, `widths` (pscale = width / 2), `ids`, `velocities`, `normals`, and every primvar with one value per point. |
| **USD Prim: PointInstancer** | `positions`, `orientations`, `scales`, `ids`, `velocities`, `protoIndices` (as `source_proto`), and its primvars. |

A USD prim is read in **world space** (its parents' transforms are applied) at the current frame plus the **Time Offset**; time samples are interpolated by USD. The node follows the timeline, so scrubbing, rendering a frame range and animated sources work.

## Controls

* **Use Percent Of Points** (+ seed): a percentage of the source points. Each id has its own fixed random number, so raising the percentage only ever **adds** points and the others keep their prototype and look.
* **Instance Ids**: **From Source Attribute** (default `id`, a POP simulation's id) keeps a particle's prototype, random variation and overrides for as long as it lives; **Point Number** uses the point order. A missing or non-unique attribute falls back to the point number with a warning, and the read-out says which was used.
* **Scale**: Off, or From Attribute (`pscale`, a radius, or a vector `scale`; the default name finds `scale` on a PointInstancer source) times the **Scale Multiplier**. It multiplies the Variation tab scale and the bank row scales. Scale Off with a multiplier scales every instance.
* **Orientation**: Upright, **From Orient Attribute** (quaternion), **Along Velocity** (+Z follows `v`; a point that is not moving stays upright) or **From Normal** (+Y follows `N`). Look > Randomize turns the instance in its own frame afterwards.
* **Copy Attributes**: names of source attributes to keep on the points (for example `Cd age temperature`).

## Prototype percentages

Source tab, *Selection Mode*:

| Mode | Behaviour |
| --- | --- |
| Random / Cycle | equal shares |
| Weighted Random | by *Weight*, statistical (a few percent of noise) |
| Sequential | blocks of the point order |
| **Even Percent** (new) | by *Weight*, **nearly exact** for any set of ids: a low-discrepancy sequence of the id (Fibonacci hashing in integer arithmetic) picks the prototype, so 1,000 points with weights 3 and 7 give 300 and 700 (within 2), the pick of every id is stable when other points come or go, and it stays on target after Use Percent Of Points thins the source. |

The **Share Of The Points** read-out shows the percentage of each prototype.

## IDs for AOVs and mattes

Tick in the Optimize tab (PRIMVARS): **arraytron_id** (the instance id, follows *Instance Ids*), **prototype_id** (the Prototype Bank row), **source_id** (always the source's own id, or the point number when it had none), **random** (stable per id), and **Copy Attributes As Primvars** for any source attribute. Houdini's standard primvar names apply: `Cd` becomes `primvars:displayColor`, and `v` becomes `primvars:velocities` in Houdini 22 and stays `primvars:v` in 20.5 / 21. In a MaterialX material read a primvar with `geompropvalue` and route it to a Karma render var (an AOV), for example the id as a matte or a per-particle colour. (This recipe is not rendered in the tests; the primvars themselves are checked value by value.)

## Evidence

`tests/validate_imported.py` (13 groups, run with hython 22, 20.5 and 21): the interface and stage order, every v1.1.0 parameter unchanged, modes 0, 1, 7 and the selection modes identical to v1.1.0, the pure functions (ids, percent, scale, alignment against rotation matrices), a VEX-generated animated "simulation" followed at frames evaluated out of order (positions, ids; the look and prototype stay with the id), id fallbacks with warnings, Use Percent against an own splitmix64 hash, every scale and orientation mode against closed-form values, USD Points and PointInstancer sources in a transformed parent (world space, widths, ids, interpolated time samples, offset, primvars, readable errors), Even Percent counts and the rule per id, primvars and copied attributes per frame, and Mask, Separation, overrides, Field Stack and Debug working on imported points. Seven mutations (`ARRAYTRON_MUTATE=imp_ids|imp_percent|imp_scale|imp_velocity|imp_normal|imp_widths|imp_idattr`) fail it. `tests/validate_h205.py` compares the imported demo (frames 1, 17, 48, 96) between Houdini 22 and 20.5 / 21: identical instancers.

## Demo

`dist/Arraytron_v1.5.0_imported_demo.hip` (and `otls_h205/Arraytron_v1.5.0_H205_imported_demo.hip`; also a network of the all-demos scene): 1,800 animated particles of a fake fountain in `/obj/fx_sim/sim` carry 30% firs and 70% rocks (Even Percent), scale from `pscale`, oriented along the velocity, ids kept (`arraytron_id`, `source_id`) and `age` copied as a primvar. Render: `renders/arraytron_v1.5.0_imported_demo_xpu.png` (frame 48).

## Limits

SOP points are used as stored (put an Object Merge / Transform in the source network to move them); only float and integer point attributes can be copied (no strings); up to 2,000,000 source points; a changing point count without a stable id attribute changes the ids (use a real id). The viewport look of the new section is unverified (GUI); the Karma AOV recipe is documented, not rendered here.
