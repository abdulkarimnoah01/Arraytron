# Master plan mapping (Claude, 2026-10-04)

Source of truth for the long-term direction: `Arraytron_Master_Solaris_Instancer_Prompt.md` (project root). This file maps it onto what exists, fixes the version ladder, and records decisions. Read the master prompt first; this file never overrides it.

## Principles carried into every version
Reliability, USD correctness, Solaris-native behaviour, artist usability, performance, maintainability, in that order. Keep one reusable pipeline (generate, process, assign prototype, compile to a native PointInstancer); never rebuild the tool per distribution. No parameter walls: new controls go into conditional folders. Every step is accepted on executed evidence (hython checks with a mutation self-test, USD inspection, a Karma XPU render) plus the user's GUI look. Specialist output (Codex, Gemini) is proposals only.

## Where the project stands against the master pipeline

| Master stage | Today (v0.21) | Gap |
| --- | --- | --- |
| 1 Prototype Bank | **v0.3 done**: multiparm bank, four source methods, weights, Random/Weighted/Sequential/Cycle, per-entry scale/scale random/rotation offset | Attribute/Mask/Noise driven selection (v0.5+), enable/LOD/collision radius per entry, variants, nested instancers |
| 2 Distribution Engine | Line (By Count/By Spacing), Area, Grid / Matrix, **Circle / Radial (v0.35)** | Concentric/Spiral/multiple rings, Curve, Surface, Volume, Existing Points, Cluster, Noise, Pattern; Line start/end trim; Grid stagger/pattern |
| 3 Paint / Mask input | none | v0.5 masks, v0.6 brush |
| 4 Field Stack | none | v0.7 |
| 5 Filtering | none | height/slope/normal/distance (v0.7) |
| 6 Alignment | Instance rotation; **`p@align` hook (v0.35)** written by Circle Facing (Outward/Center/Tangent), composed last in `VARIATION_PROCESSOR` | Curve/Surface write the same attribute in v0.4; up vector, face camera, normal blend |
| 7 Variation | **v0.3.6 done**: position jitter, Euler or Yaw-Only rotation variation, Fraction or Min/Max scale, per-axis Non-Uniform scale, axis locking by 0 (id-keyed random streams) | scale ramps, mask/noise/prototype-driven variation (v0.5+), full-sphere random orientation |
| 8 Collision / Relaxation | **v0.4.0 Physics Settle**: stones collide with each other and with ground/collider prims through Houdini Bullet, then are frozen | Non-physics minimum separation / clustering / relaxation for ordinary distributions stay v0.8 |
| 9 Prototype Assignment | **v0.3 done**: `PROTOTYPE_ASSIGNMENT` stage, stable `proto_id` | selection driven by attributes/masks/noise |
| 10 USD Compiler | native PointInstancer, shared prototypes, Bounds Transform xform, guide | primvars, hierarchy review (v0.9), overrides (v1.0) |
| Stable IDs | ids deterministic per generator; random streams keyed by id; weighted selection reshuffles only boundary points (v0.3) | overrides database (v1.0) |
| Debug | Bounds Guide only | debug views (grow with each stage) |
| UI | Source / Distribution / mode folders / Bounds Transform / Instance Transform / Randomize | Basic/Advanced split once there are enough controls |

Already built beyond the master text: the shared Bounds Transform (Position/Rotation/Scale/Pivot, viewport handle, Scale Instances toggle), Bounds Guide, Keep Inside Area, read-only count/spacing readouts.

## Version ladder going forward

> Naming update (2026-10-04): releases are now plain `vMAJOR.MINOR.PATCH` (see `docs/VERSIONING.md`). In the table below v0.3 = v0.3.0, v0.35 = v0.3.5, v0.4 = v0.4.0, v0.5 = v0.5.0 and so on.
The early versions were numbered ad hoc (0.15, 0.16, 0.2, 0.21). From here follow the master roadmap numbers. HDA type versions use two digits after the dot (`0.30`, `0.40`, ...) so Houdini's component-wise numeric version sort stays correct.

| Version | Content (master roadmap, adjusted) |
| --- | --- |
| v0.3 | Modular refactor of the internal network (named processor stages), Prototype Bank multiparm, weighted selection, Random/Weighted Random/Sequential/Cycle, stable prototype ids |
| v0.35 (small) | Circle / Radial (completes the master's v0.2 list) and the shared variation processor (yaw-only, axis lock, ranges) |
| v0.4.0 (user request, 2026-10-12) | **Physics Settle**: optional Bullet rigid-body settle of any distribution, cached, fed to the same PointInstancer (done; docs/PHYSICS_SETTLE.md) |
| v0.4.5 | **Curve** (done 2026-10-12) with tangent alignment through the shared `p@align` hook. These were the master roadmap's v0.4; they moved to the .5 sub-steps so v0.5 to v1.0 keep their numbers |
| v0.4.6 | **Surface Scatter** (done 2026-10-12): area-weighted stable scatter on stage meshes, normal alignment, slope limits, density; stage geometry is read with pxr from a prim path (docs/CURVE_SURFACE.md) |
| v0.5 | Mask input architecture: **v0.5.0 done 2026-10-12** (Noise, Image, Mesh Primvar sources; Density / Scale; one weight per point, any mode); painted density waits for the v0.6 brush; **v0.5.1 No Overlap done** (a step towards v0.8 minimum separation: Remove / Push Apart on bounding spheres) |
| v0.6 | Real viewport brush (Python Viewer State), stroke storage, add/remove: **v0.6.0 done 2026-10-12** (Paint mode, Add / Remove, radius, strength, density, spacing, falloff, surface projection; docs/PAINT_BRUSH.md; the tool in a real viewport is unverified) |
| v0.7 | Field Stack, height/slope/noise/distance, exclusion geometry |
| v0.8 | Clustering, minimum separation, simple collision |
| v0.9 | Camera optimisation, LOD/proxy, extended primvars |
| v1.0 | Stable-id overrides, refined paint, caching, debug system, documentation |

## Facts established by probing Houdini 22.0.368 (not assumptions)
- The native PointInstancer LOP takes several prototype prims through `protopattern` (space-separated paths). It authors each as a reference under `<output>/Prototypes/<name>`, in pattern order, hides the sources, and `protoIndices` follow an integer point attribute (`protoindex`) indexed in that same order. A string-attribute mode (`strattr`) exists too. Probe: `team/` scratch run on 2026-10-04 (3 cubes, 9 points, indices 0,1,2 repeating, no errors).
- Behaviours still to probe when building the bank: two prototypes with the same prim name under different parents, a disabled or missing entry in the middle, and renaming/reordering rows.

## Decisions and open questions for the user
1. **Circle placement.** The master's v0.2 listed Grid and Circle; Grid is done, Circle is not. Section 34 of the master puts Prototype Bank first, so Circle moves to a small v0.35. Say if you want it earlier.
2. **Brush painting (v0.6) needs the Houdini GUI** (a Python Viewer State cannot be exercised headlessly). I will not drive your GUI without asking; I will prepare the state and tests and ask you for GUI sessions, or run my own separate Houdini window only with your say-so.
3. **Surface Scatter input (v0.4).** DECIDED and built in v0.4.5 / v0.4.6: a prim path in the incoming stream read with pxr (no second input, no SOP path; SOP geometry can be brought in with a SOP Create LOP).
4. **Basic/Advanced UI.** Houdini has no built-in mode switch; the plan is an Advanced toggle that reveals folders by conditional visibility, introduced once the control count justifies it.
5. **Gemini** is still unavailable (no `agy` CLI). Test cases are written and run by Claude, flagged as not reviewed by Gemini, until that client is installed.

## Progress log
- 2026-10-04: v0.3 built and validated (Prototype Bank + modular network). Probed first: the native PointInstancer takes several prototypes; HDA with 4 inputs tolerates unconnected inputs; SOP Import with an empty path is a harmless passthrough; duplicate prototype names are auto-renamed by Houdini. Source methods requested by the user for the bank: reference/direct input connection, prototype prim path, USD from disk, SOP create input (delivered as: Input Connection through Prototype Inputs 2-4 which accepts any LOP such as a Reference or SOP Create, Prim Path, USD File, SOP Geometry via SOP path).
- 2026-10-04: v0.35 Circle / Radial built and validated. The Circle generator writes Facing as `p@align`; the variation stage composes it last, so v0.4 Curve/Surface can reuse the same shared alignment mechanism instead of each adding orientation code. The variation extras originally grouped with v0.35 (yaw-only, axis lock, ranges, non-uniform scale) were not requested and remain open; suggested home: a small v0.36 or alongside v0.4.
- 2026-10-04: v0.3.6 variation extras built and validated (Yaw Only, Scale Min/Max, Non-Uniform). Output with defaults is bit-identical to v0.3.5. First real use of tools/archive_release.py (v0.3.5 archived). Next in the master roadmap: v0.4.0 Curve / Surface Scatter / alignment (Surface input design needs research first).
- 2026-10-12: v0.4.0 Physics Settle built and validated at the user's request (not in the master roadmap order; the roadmap's own collision step v0.8 stays for non-physics relaxation). Optional, off by default, output bit-identical to v0.3.6 when off. Curve / Surface Scatter move to v0.4.5 / v0.4.6; v0.3.6 archived. Details: docs/PHYSICS_SETTLE.md.
- 2026-10-12: v0.4.5 Curve and v0.4.6 Surface Scatter built and validated (docs/CURVE_SURFACE.md). v0.4.0 and v0.4.5 archived. Next in the master roadmap: v0.5 mask input architecture.
- 2026-10-12: v0.5.0 Mask pipeline and v0.5.1 No Overlap built and validated (docs/MASKS_AND_OVERLAP.md); v0.4.6 and v0.5.0 archived. Physics demos rebuilt for the current release (railway and box). Next: v0.6 viewport brush.
- 2026-10-12: v0.5.2 six-tab interface and Grow animation (docs/INTERFACE_AND_GROW.md); v0.5.1 archived. Not in the master roadmap order: requested by the user. Next: v0.6 viewport brush.
- 2026-10-12: v0.6.0 viewport brush and clearer input labels (docs/PAINT_BRUSH.md); v0.5.2 archived. Next: v0.7 Field Stack.
- 2026-10-12: v0.7.0 Field Stack (docs/FIELD_STACK.md): Height, Slope, Noise, Image, Distance, Exclusion fields with Multiply / Add / Subtract / Min / Max; v0.6.0 archived. Painted-mask, curvature and normal-direction fields are not in it. Next: v0.8.
- 2026-10-12: v0.8.0 Cluster mode, minimum separation (the v0.5.1 No Overlap, now with Priority) and simple collision (Avoid Geometry) in one Separation & Collision stage (docs/CLUSTER_AND_SEPARATION.md); v0.7.0 archived. Next: v0.9.
- 2026-10-12: v0.9.0 camera optimisation, LOD / proxy handling and extended primvars (docs/CAMERA_LOD_PRIMVARS.md); v0.8.0 archived. Next: v1.0 production polish.
- 2026-10-12: v1.0.0 production release: stable-id audit, manual instance overrides, Paint Replace / Relax, debug system, USD export and caching strategy, production tests, documentation; v0.9.0 archived. The master roadmap is complete; open items are the GUI checks.
- 2026-10-12: v1.1.0 Houdini 20.5 / 21 build (docs/PORT_HOUDINI_205.md): the same node on the older Instancer LOP with identical USD output, installer for 20.5 / 21 / 22; v1.0.0 archived. A compatibility release outside the master plan; open items are the GUI checks.
- 2026-10-14: v1.5.0 Imported Points (user request after the roadmap: scatter on imported FX sim points / any points with full control of prototype percentages, scale, rotation and ids for AOVs), docs/IMPORTED_POINTS.md; v1.1.0 archived.
- 2026-10-15: v1.6.0 Paint tool shortcuts (user request after the first working GUI test of the brush); v1.5.0 archived.
