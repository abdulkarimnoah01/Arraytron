# Falloff (v1.12.0)

A scatter that is **full size and densest in the centre** and fades towards the edges: the scale shrinks and the density thins out. The section **FALLOFF** is on the Layout tab, below *Move The Layout*, and works with **every Distribution Mode** (Line, Area, Grid, Circle, Curve, Surface, Cluster, Imported Points ...). Off by default: with Falloff off the output is exactly the previous release.

| Control | Meaning |
| --- | --- |
| Falloff | Master switch. |
| Shape | **Radial (circle)**: the distance from the centre divided by the reach. **Box (every edge)**: the largest of the offsets along the axes divided by the half size of the layout, so *every* edge of a rectangle fades, not only its corners. |
| Curve | How the weight falls from 1 in the centre to 0 at the edge: Linear, Smooth (smoothstep) or Gaussian. |
| Flat Centre (%) | The central part of the reach that keeps full size and full density before the fade starts. |
| Edge Density (%) | The share of the points that is kept at the edge. **0** (default): the density falls to nothing at the edge. **100**: the density does not change (only the scale falls). |
| Edge Scale | The scale at the edge as a fraction of the true scale (default 0.2; the centre keeps the true scale). **1**: the scale does not change (only the density falls). |

**Falloff Details:** *Axes* (X and Z, the ground plane, by default, or X, Y and Z); *Centre* (automatic = the middle of the bounding box of the generated points, or a custom position); *Reach* (automatic = the distance of the farthest generated point, or a custom radius, which also keeps the falloff steady while you change the count); *Falloff Seed*. A read-out shows the centre, the reach and how many points were kept.

**How it works.** Every point gets a normalised distance t (0 in the centre, 1 at the edge), the Curve turns it into a weight w, then
* the **density**: a point survives when its own random number (keyed on its id, like the Mask) is below `edge density + (1 - edge density) * w`, so a bigger weight, a bigger reach or a higher edge density only ever **adds** points and a survivor never moves;
* the **scale**: `edge scale + (1 - edge scale) * w` is multiplied into the Mask Scale (`f@maskscale`), which the Prototype Assignment applies last, after the Look tab scale, the Prototype Bank scale and the Variation.

It runs after the Mask and the Field Stack (their removals and scales are kept and multiplied) and before the Variation, the Separation and the Physics, so Separation works on the thinned, shrunk instances. Positions are in the space the points are generated in: the layout space of Line, Area, Grid and Circle (the Bounds Transform is applied afterwards, so the falloff moves with the layout), the world space of Surface, Cluster and Imported Points, like the Field Stack.

**Notes.** *Circle* mode puts the points on a ring, so every point has the same distance from the centre and a radial falloff makes the whole ring uniformly small; use a *Custom* centre or reach (off-centre, to fade across the ring) or the Surface / Area mode for a disc. *Surface* mode scatters over the whole surface: use a Custom centre and reach to pick the patch that should fade (the reach then also bounds the scatter when Edge Density is 0). *Cluster* mode has its own falloff around every cluster centre; this one fades the whole layout. Paint and Instance Place are explicit placements, so use the stage only if you really want it to thin them.

## Evidence and limits

`tests/validate_falloff.py` (6 groups, 6 mutations): the curves, the flat centre and the radial / box / XYZ distances against independent formulas, custom centre and reach, the id-keyed survival (statistics, subset, only ever adds), the scale multiplier on Area (per point), Box (every edge), Line, Grid, Circle (the ring) and Surface (world space), the Mask multiplying, off reproducing the previous release, and the interface and stage order. How the section looks on the Layout tab is for the user to judge.

Demo: `dist/Arraytron_v1.12.0_falloff_demo.hip` (render `renders/arraytron_v1.12.0_falloff_demo_xpu.png`): three patches of rocks side by side: no falloff, radial and box.
