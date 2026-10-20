# Falloff (v1.12.0)

A scatter that is **full size and densest in the centre** and fades towards the edges: the scale shrinks and the density thins out. The section **FALLOFF** is on the Layout tab, below *Move The Layout*, and works with **every Distribution Mode** (Line, Area, Grid, Circle, Curve, Surface, Cluster, Imported Points ...). Off by default: with Falloff off the output is exactly the previous release.

| Control | Meaning |
| --- | --- |
| Falloff | Master switch. |
| Region | **Automatic (follows the mode)**: Cluster fades every cluster to its own boundary, Paint fades across the width of every stroke path, Grid uses all three axes when it has layers in Y; every other mode the whole layout. **Whole layout**: one centre and one reach for everything, like v1.12.0. |
| Shape | **Radial (circle)**: the distance from the centre divided by the reach. **Box (every edge)**: the largest of the offsets along the axes divided by the half size of the layout, so *every* edge of a rectangle fades, not only its corners. |
| Curve | How the weight falls from 1 in the centre to 0 at the edge: Linear, Smooth (smoothstep) or Gaussian. |
| Flat Centre (%) | The central part of the reach that keeps full size and full density before the fade starts. |
| Edge Density (%) | The share of the points that is kept at the edge. **0** (default): the density falls to nothing at the edge. **100**: the density does not change (only the scale falls). |
| Edge Scale | The scale at the edge as a fraction of the true scale (default 0.2; the centre keeps the true scale). **1**: the scale does not change (only the density falls). |

**Falloff Details:** *Axes* (a 3D Grid always uses all three with Region Automatic) (X and Z, the ground plane, by default, or X, Y and Z); *Centre* (automatic = the middle of the bounding box of the generated points, or a custom position); *Reach* (automatic = the distance of the farthest generated point, or a custom radius, which also keeps the falloff steady while you change the count); *Falloff Seed*. A read-out shows the centre, the reach and how many points were kept.

**The region follows the mode (Region: Automatic, v1.13.0).**
* **Cluster:** every cluster has its own centre and radius (the Cluster generator now writes them on every member as `ccentre` and `cradius`), so each member is faded against *its own* cluster boundary, not against the box or circle around all of them: the outermost cluster is full size in its own centre. Radial = the distance to the cluster centre divided by its radius; Box = a square of the cluster radius.
* **Paint:** the viewport brush now records the path of every Add and Replace stroke (the dab centres, thinned, and the brush radius; stored in the Paint Data as the `p2` format, 2000 strokes at most). The falloff is the distance of a point to the **nearest stroke path** divided by that stroke's brush radius: full size and density along the path, fading to the edge across the width of the stroke, so two crossing strokes blend naturally. A scene painted before v1.13.0 (or with scripted dabs) has no stroke paths: it uses the whole layout, and points that no recorded stroke reaches keep their full size (the read-out says how many). Paint again, or use `paint_stroke_add`, to record paths. Erase and Relax strokes record nothing; Clear Paint clears the paths.
* **Grid:** a Grid with more than one layer in Y (a 3D matrix) fades in all three axes, so its top and bottom boundaries count as well as its sides; with the Box shape every face of the matrix fades. A single layer stays on the ground plane. (Region Whole layout and the Axes menu give the old behaviour.)

**How it works.** Every point gets a normalised distance t (0 in the centre, 1 at the edge), the Curve turns it into a weight w, then
* the **density**: a point survives when its own random number (keyed on its id, like the Mask) is below `edge density + (1 - edge density) * w`, so a bigger weight, a bigger reach or a higher edge density only ever **adds** points and a survivor never moves;
* the **scale**: `edge scale + (1 - edge scale) * w` is multiplied into the Mask Scale (`f@maskscale`), which the Prototype Assignment applies last, after the Variation tab scale, the Prototype Bank scale and the Variation.

It runs after the Mask and the Field Stack (their removals and scales are kept and multiplied) and before the Variation, the Separation and the Physics, so Separation works on the thinned, shrunk instances. Positions are in the space the points are generated in: the layout space of Line, Area, Grid and Circle (the Bounds Transform is applied afterwards, so the falloff moves with the layout), the world space of Surface, Cluster and Imported Points, like the Field Stack.

**Notes.** *Circle* mode puts the points on a ring, so every point has the same distance from the centre and a radial falloff makes the whole ring uniformly small; use a *Custom* centre or reach (off-centre, to fade across the ring) or the Surface / Area mode for a disc. *Surface* mode scatters over the whole surface: use a Custom centre and reach to pick the patch that should fade (the reach then also bounds the scatter when Edge Density is 0). *Cluster* mode has its own **Cluster Falloff** (the distribution of members inside a cluster); this stage fades the clusters' scale and density towards each cluster's boundary on top of it. Paint and Instance Place are explicit placements, so use the stage only if you really want it to thin them.

## Evidence and limits

`tests/validate_falloff.py` (10 groups, 10 mutations; the Cluster, Grid and Paint regions are checked against independent distances, and Region Whole layout against v1.12.0): the curves, the flat centre and the radial / box / XYZ distances against independent formulas, custom centre and reach, the id-keyed survival (statistics, subset, only ever adds), the scale multiplier on Area (per point), Box (every edge), Line, Grid, Circle (the ring) and Surface (world space), the Mask multiplying, off reproducing the previous release, and the interface and stage order. How the section looks on the Layout tab is for the user to judge.

Demo: `dist/Arraytron_v1.13.0_falloff_demo.hip` (render `renders/arraytron_v1.13.0_falloff_demo_xpu.png`): front row, three Area patches: no falloff, radial and box; back row: two paint strokes fading across their width, five clusters each fading to its own boundary, and a 3D grid fading to all its faces.
