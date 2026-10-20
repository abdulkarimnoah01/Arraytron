# Arraytron roadmap (Claude leading, 2026-10-04)

Principle: keep it "choose a prototype, choose a mode, adjust a few parameters, get a clean PointInstancer". Every step ends with executed Houdini checks, a Karma XPU render and a real look at the parameter pane/viewport. Specialist output is proposals only (`docs/TEAM_ROSTER.md`).

## 1. Close v0.15 (now)
- User runs Codex's GUI checklist (`team/v015-codex-artist/response.md`, section 3) on `dist/archive/Arraytron_v0.1.5_demo.hip`: parameter pane, guide curves visible, handle drags, Reset button.
- Fix whatever that finds. Re-run `tests/validate_v015.py` and the Karma render.
- Gemini writes test cases/expected results once its client works; Claude implements and runs them. Until then Claude writes them and marks them as not reviewed by Gemini.
- Then v0.15 is accepted and frozen.

## 2. v0.16: small artist wins inside Line + Area (DONE 2026-10-04)
- Keep position jitter inside the Area bounds (optional toggle, default off). Deferred from Codex's review.
- Line "By Spacing" mode (in the original brief as optional): Count derived from Length and Spacing; the read-only Spacing display from v0.15 becomes editable there.
- Anything the user's GUI review turns up.

## 3. v0.2 Grid / Matrix (DONE 2026-10-04, awaiting GUI review); later distributions follow the user master plan
Reuse the existing pipeline (generate points, modify transforms, assign prototype, native PointInstancer). Suggested order: Grid, Circle, Curve (from an input curve), Surface scatter, Volume, Custom Points, then multiple weighted prototypes. One at a time, each with the same Bounds Transform, guide, handle and validation pattern.

## Team loop per step
Codex plans and plays the artist, Claude implements/reviews/runs, Gemini supplies test cases and expected results, Claude decides and records verdicts in `team/<phase>/lead_review.md`.

Status 2026-10-04: v0.16 (Line By Spacing, Keep Inside Area) and v0.2 (Grid / Matrix) are built and validated. The user will supply the plan for the master version next.

Status 2026-10-04 (later): v0.21 adds Scale Instances (default off) so a non-uniform Bounds Scale cannot stretch the instances by accident. Next: the user master-version plan.

Status 2026-10-04 (latest): master plan adopted (docs/MASTER_PLAN_MAP.md). v0.3 Prototype Bank + modular refactor built and validated. Next per the master roadmap: v0.35 Circle/Radial + shared variation processor, then v0.4 Curve/Surface/alignment.

Status 2026-10-04 (latest): v0.35 Circle / Radial built and validated. Next per the master roadmap: shared variation extras (small), then v0.4 Curve / Surface Scatter / alignment.

Status 2026-10-04 (latest): versioning moved to plain vMAJOR.MINOR.PATCH ids (docs/VERSIONING.md); the current release is v0.3.5, older ones are in dist/archive/.

Status 2026-10-04 (latest): v0.3.6 variation extras built and validated. Next per the master roadmap: v0.4.0 Curve / Surface Scatter / shared alignment.

Status 2026-10-12 (latest): v0.4.0 Physics Settle built and validated at the user's request (see docs/PHYSICS_SETTLE.md); the master roadmap's Curve / Surface Scatter / shared alignment step moves to v0.4.5 / v0.4.6. Next: those two (Surface Scatter still needs the decision on how the HDA reads stage geometry; the Physics Settle collider reader already shows one working way: pxr on the incoming stage).

Status 2026-10-12 (latest): v0.4.5 Curve and v0.4.6 Surface Scatter built and validated (docs/CURVE_SURFACE.md). Next per the master roadmap: v0.5 mask input architecture (one reusable mask / field pipeline: SOP attribute, USD primvar, texture, painted density), which Surface Scatter and Curve will plug into.

Status 2026-10-12 (latest): v0.5.0 Masks and v0.5.1 No Overlap built and validated (docs/MASKS_AND_OVERLAP.md). Next per the master roadmap: v0.6 viewport brush (Python Viewer State, GUI dependent), which will paint the same 0 to 1 mask value; v0.7 Field Stack (height / slope / distance fields) can feed the mask pipeline too.

Status 2026-10-12 (latest): v0.5.2 six-tab interface and Grow animation built and validated (docs/INTERFACE_AND_GROW.md). Next per the master roadmap: v0.6 viewport brush (GUI dependent); it will get its own section in the Look tab.

Status 2026-10-12 (latest): v0.6.0 viewport brush built and validated (docs/PAINT_BRUSH.md); the tool itself is GUI-unverified. Next per the master roadmap: v0.7 Field Stack.

Status 2026-10-12 (latest): v0.7.0 Field Stack built and validated (docs/FIELD_STACK.md). Next per the master roadmap: v0.8.

Status 2026-10-12 (latest): v0.8.0 Clustering, Separation and Collision built and validated (docs/CLUSTER_AND_SEPARATION.md). Next per the master roadmap: v0.9 (camera optimisation, LOD, proxies, extended primvars).

Status 2026-10-12 (latest): v0.9.0 camera optimisation, LOD / proxies and extended primvars built and validated (docs/CAMERA_LOD_PRIMVARS.md). Next per the master roadmap: v1.0 production polish.

Status 2026-10-12 (latest): v1.0.0 built and validated (docs/OVERRIDES_DEBUG_EXPORT.md): the master roadmap v0.1 to v1.0 is complete; further work follows the user's review.

Status 2026-10-12 (latest): v1.1.0 adds the Houdini 20.5 / 21 build (docs/PORT_HOUDINI_205.md); the master roadmap v0.1 to v1.0 stays complete; further work follows the user's review.

Status 2026-10-14 (latest): v1.5.0 Imported Points built and validated in Houdini 22, 20.5 and 21 (docs/IMPORTED_POINTS.md). The master roadmap v0.1 to v1.0 stays complete; further work follows the user's review.

Status 2026-10-15 (latest): v1.6.0 Paint shortcuts built and validated in Houdini 22, 20.5 and 21 (docs/PAINT_BRUSH.md).

Status 2026-10-15 (latest): v1.6.1 fixes the Paint tool switching the Distribution Mode when the node is selected.

Status 2026-10-18 (latest): v1.6.2 renames the Settle tab to Physics.

Status 2026-10-18 (latest): v1.7.0 adds Pick Instance (viewport picking of instance ids for the overrides).

Status 2026-10-18 (latest): v1.8.0 adds the built-in LOD generator.

Status 2026-10-19 (latest): v1.9.0 adds the Instance Place distribution mode.

Status 2026-10-20 (latest): v1.10.0 adds Instance Place arrays (Copies and steps).

Status 2026-10-20 (latest): v1.11.0 adds the Place tool extras and the cleanups.

Status 2026-10-20 (latest): v1.12.0 adds Falloff (scale and density). Next: the biome sector.

Status 2026-10-20 (latest): v1.13.0 makes the Falloff follow the mode and renames the tabs. Next: the biome sector.

Status 2026-10-21 (latest): v1.14.0 adds Rows for the linear modes. Next: the biome sector.

Status 2026-10-21 (latest): v1.15.0 starts the biome sector (Biome distribution mode). Next: layers (canopy / understory / ground cover), competition, biome map.

Status 2026-10-21 (latest): v1.16.0 adds the Effect per biome condition. Next: layers (canopy / understory / ground cover), competition, biome map.
