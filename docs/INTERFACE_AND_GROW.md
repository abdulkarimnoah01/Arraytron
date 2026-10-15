# The six-tab interface and the Grow animation (v0.5.2)

## Why the interface changed

Until v0.5.1 the node had **14 top-level tabs in one row** (Source, Distribution, Line, Area, Grid, Circle, Curve, Surface, Bounds Transform, Instance Transform, Randomize, Mask, No Overlap, Physics Settle) and about 150 parameters; the mode tabs appeared and disappeared with the Distribution Mode. v0.5.2 regroups the same parameters into **six tabs in the order an artist works**.

Codex (gpt-6-astra, medium effort) was asked for a design (`team/v052-codex-ui/`); Claude decided (verdicts in `lead_review.md` there). **Parameter names, defaults, menus and values did not change** (a test compares every parameter of v0.5.1 with the new node), so scripts, saved parameter values and the viewport handle keep working; only the containers, order and headings are new.

| Tab | What is in it, top to bottom |
| --- | --- |
| **Source** | Prototype Bank (the models), Selection Mode, Resolved Prototypes read-out, *Selection Details* (seed), OUTPUT prim path |
| **Layout** | Distribution Mode, then **only the active mode's settings** under a heading (Line / Area / Grid / Circle / Curve / Surface; the others are hidden, no tab row changes), then MOVE THE LAYOUT (Position, Rotation, Scale, Scale Instances, Reset, *Pivot & Guide*) |
| **Look** | INDIVIDUAL INSTANCES (rotation, scale), VARIATION (Randomize; *Variation Details* = non-uniform scale), MASK (source, effect, contrast, read-out; *Mask Details* = noise offset/octaves/roughness/contrast, image channel/projection/centre/size/outside, UV name) |
| **Spacing** | No Overlap (mode, size, spacing, axes, read-out; *Solver Settings* = iterations, strength) |
| **Settle** | Physics Settle (on, status, spawn, **Simulate & Cache**, drop height, overlap-free spawn, seed, maximum time, quality; *Material & Forces*, *Collision Settings*, *Cache Settings* with Clear Cache) |
| **Animate** | Grow animation |

Design rules that came out of the review: workflow order, **fixed tabs** (never a tab that comes and goes), mode panels as headings with their parameters directly below (shown by the same `mode` condition), **local disclosure** instead of a global Basic / Advanced switch, specialist settings in collapsible "... Details" sections, a one-line hint under each tab title, read-outs beside the decision they support.

**GUI-unverified:** the open/closed default state of the collapsible sections. Houdini creates collapsible folders with default value 0 everywhere (2,200 built-in examples checked), which I assume means closed; if they open expanded, nothing is hidden, only less tidy.

## Grow animation

The instances are revealed over the timeline in a **sweep across the layout**. Each instance gets a start frame from where it lies along the sweep (plus an optional random delay) and grows over *Grow Time* frames. It animates the final transforms, so Physics Settle's cache is reused and never re-simulated; a finished instance is **exactly** the normal result (bit for bit).

| Control | Meaning |
| --- | --- |
| Grow Animation | Off by default; off means no change and the node does not depend on time. |
| Sweep Direction, Custom Vector, Reverse | Along X / Y (upward) / Z, a Custom Vector, **Outward From Centre** (distance in XZ), or **By Point Order** (id order: follows a Line or Curve from start to end). The position along the sweep is measured once from each instance's *final* position, in the space of the generated points (before the Bounds Transform; world space with Physics Settle), so the order never changes while things move. |
| Start Frame | Default `$FSTART` (the start of the playback range). |
| Sweep Duration | Frames the start takes to travel from the first to the last instance (default 48; 0 = all together). |
| Grow Time | Frames each instance takes to reach full size (default 12). |
| Random Delay, Delay Seed | A stable random extra delay per id, up to this fraction of (Sweep Duration + Grow Time). |
| Style | **Grow**: uniform scale up about the model origin. **Plant**: height first (done at 70% of the time), width follows (from 20%). **Rise**: the instance keeps its size and climbs *Rise Distance* out of the ground, scaling in over the first 30%. Models grow about their origin: author plants with the origin at the base. |
| Easing | Linear, Smooth (default), **Overshoot (pop)**, **Bounce**; every curve ends exactly at the normal transform. |
| Read-out | When the first instance starts and the last one is full size. |

Not-yet-started instances are hidden twice: their scale is vanishingly small **and** they are listed in the PointInstancer's `invisibleIds` (written by the guide Python LOP at the current frame; the PointInstancer's own invisibleIds importer, which writes an empty list, is switched off while Grow is on). While Grow is on a green **arrow guide** shows the sweep direction (none for Outward / By Point Order).

Because the node is evaluated at the current frame, scrubbing the timeline, the viewport and a Karma render of a frame range all show the animation. It is not looped (planned, not built).

## Evidence

`tests/validate_grow.py` (8 groups): the six-tab structure (every parameter of v0.5.1 present once with the same default and menu, details sections, the 12 handle bindings), Animate defaults and conditionals, output with Grow off equal to v0.5.1 at any frame and the node not time dependent, **exact per-frame scales and invisibleIds** (frames before, during and after the sweep; Reverse; Sweep 0; negative start; frames evaluated out of order), the six directions against projections of the final positions, all four easing curves and the Plant and Rise styles against independent formulas, exact end states, the random delay against an independent hash, and Grow combined with a settled Physics Settle cache, a mask, No Overlap and the arrow guide. 5 mutations (`ARRAYTRON_MUTATE=grow_order|grow_ease|grow_time|grow_final|grow_style`) each fail it. The main (39), physics (19), scatter (24), mask (11) and overlap (6) suites pass on v0.5.2 with the new interface. Karma XPU: `renders/arraytron_v0.5.2_grow_demo_xpu.png` (frames 1, 24, 44, 64, 84, 110: firs growing in from the left edge, crates popping up from the middle).

## Limits

* No looping or ping-pong yet; one sweep per node; a single start / end per node (no per-axis timing).
* Positions are not animated except by Rise; Plant and Grow change scale only.
* The interface is checked by tests (structure, conditionals, defaults); how it looks and feels in the parameter pane is not verified.
