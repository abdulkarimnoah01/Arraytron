# Clustering, Separation and Avoid Geometry (v0.8.0)

v0.8.0 adds **Cluster** as a Distribution Mode and turns the old **No Overlap** stage into one **Separation & Collision** stage (Spacing tab). Nothing was duplicated: the v0.5.1 No Overlap controls (Remove / Push Apart, Size From, Radius, Spacing, Measure In, Iterations, Strength) are the Separation controls, with the same parameter names and defaults, and the two things the master plan asked for beyond them (priority, collision with scene geometry) were added to the same stage. With Avoid Geometry off and Priority on Id Order, v0.8.0 produces exactly what v0.7.0 did (tested).

## Cluster (Layout tab, Distribution Mode Cluster)

Groups of instances around centres that are scattered over a surface.

| Control | Meaning |
| --- | --- |
| Cluster Surface | A prim in the Scene Stream (mesh or basic shape; hills are followed). Empty = a flat ground rectangle at Y = 0 (Ground Size, centred on the origin). |
| Cluster Count | Number of clusters. Centres use Surface Scatter's sampler (area weighted), so cluster c never moves when the count changes. |
| Instances Per Cluster | Average members (at most 999 each, 20,000 in total). |
| Cluster Radius | Size of a cluster. |
| Cluster Falloff | 0 fills the disc evenly, 1 packs the members towards the centre (radial distance = radius x u^(0.5 + 1.5 x falloff)). |
| Cluster Jitter | Random variation of every cluster's size and member count (0.3 = +/- 30%). |
| Seed, Normal, Align to Normal, Offset | As in Surface Scatter. |

Members are projected onto the surface (members that fall off an edge are dropped). Ids are `cluster x 1000 + member`, so adding clusters or members never renames the points that exist; every later stage (Mask, Field Stack, Variation, Separation, Physics Settle, Grow) keys on these ids. The cluster number is also written as `cluster` on the points.

Clusters work with the Field Stack and the Mask as the master plan asks: for example a Slope field removes the members that land on steep ground, Noise makes some clusters thinner.

## Separation (Spacing tab)

Same controls as No Overlap in v0.5.1 (instances are bounding spheres from the prototype, or a Fixed Radius, kept `Spacing` x (r1 + r2) apart; Remove Overlapping or Push Apart), plus:

* **Priority** (Remove Overlapping): which of two overlapping instances survives. *Id Order* (default, as before), *Biggest First*, *Smallest First*, *Random* (a fixed random order from the id). Ties go to the earlier point.

## Avoid Geometry (Spacing tab)

Keeps instances out of scene geometry (a hero prop, a building, a road curve).

| Control | Meaning |
| --- | --- |
| Avoid Geometry | Off, **Remove** (delete colliding instances) or **Push Out** (move them away from the nearest surface point until clear). |
| Avoid Prim | A mesh, shape or curve (or a prim above some) in the Scene Stream, at its world transform. |
| Margin | Clearance beyond the instance radius. |
| Measure In | XYZ: 3D distance, and a centre inside a closed mesh counts as colliding (it is pushed out through the nearest face). XZ: the building's footprint, heights ignored. |
| Iterations | Push Out passes. |

An instance collides when its centre is closer than radius + Margin to the geometry (radius from Size From, times the instance scale). Order of work: Avoid Geometry first, then Separation; when both push, a last Push Out pass runs so that the geometry always wins. A read-out under the stage says how many points were removed or moved.

## Demo

`dist/Arraytron_v0.8.0_cluster_demo.hip` (render `renders/arraytron_v0.8.0_cluster_demo_xpu.png`): 16 clusters of firs on the terrain, a Slope field keeping them off the steep bank, Separation (Remove, Biggest First) and Avoid Geometry (Push Out) around the pond sphere. It is also a network in `dist/Arraytron_v0.8.0_all_demos.hip`.

## Evidence

`tests/validate_cluster.py` (8 groups): the interface, modes 0, 1 and 5 identical to v0.7.0, member counts and radius factors, centres equal to Surface Scatter's sampler, members inside their cluster radius, ids, clusters stable when more are added, the radial law for falloff 0 / 0.5 / 1, clusters on a curved surface (on it, aligned, offset), a readable error for a missing prim, and Field Stack / Separation / Grow working on clusters. Six mutations (`ARRAYTRON_MUTATE=cluster_falloff|cluster_stride|cluster_jitter|cluster_project|cluster_centres|cluster_radius`) fail it. `tests/validate_avoid.py` (7 groups): Id Order and Avoid-off identical to v0.7.0 (Remove, Push Apart, XZ), every Priority against a plain-Python greedy removal (with ties, XZ and XYZ), Avoid Geometry against the analytic box (Remove, Push Out, inside points, XZ footprint), the node end to end (survivors, clearance, untouched points, ids, Separation after Push Out) and Priority on the node. Six mutations (`avoid_margin|avoid_inside|avoid_push|avoid_axes|avoid_priority|avoid_random`) fail it, and the five No Overlap mutations still fail `validate_overlap.py`. The main (39), physics (19), scatter (24), mask (11), overlap (6), grow (8), paint (16) and fields (16) suites pass on v0.8.0.

## Not verified / limits

The look of the Layout and Spacing tabs in the parameter pane (GUI). A cluster is a disc, not an irregular blob; members are placed independently (no minimum distance inside a cluster, use Separation for that). Avoid Geometry uses sphere against geometry distance, not full shape against shape, and Push Out can leave a small residual in tight spots (the read-out shows it). Inside / outside needs a closed mesh. Curves are avoided by distance only. A cluster surface with more than a few hundred thousand triangles will be slow (every cluster looks at the triangles near it, but the first pass reads them all).
