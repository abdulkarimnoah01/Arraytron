# Rows (v1.14.0)

The linear Distribution Modes (**Line**, **Circle / Radial**, **Curve**) scatter along ONE path. The section **ROWS** on the Layout tab (under the mode settings, shown for those three modes) lays the same path out as **several parallel rows** and can **randomise** between them. Off by default (Rows 1, no random): the output is exactly the previous release.

| Control | Meaning |
| --- | --- |
| Rows | How many rows (1 to 50). **Line**: rows next to each other. **Circle**: concentric rings. **Curve**: copies of the curve pushed to the side. The Count / Spacing of the mode is the number of points of **one row**, so the total is Rows times that. |
| Row Spacing | Distance between two rows, sideways from the path (horizontal and perpendicular to it; for a Circle in its plane, radially). |
| Centre The Rows | On (default): the rows are spread around the path (the middle one on it for an odd number of rows). Off: the path is the first row and the others follow on one side (a Circle: outwards). |
| Random Offset | 0 to 1: each point is moved sideways by a random amount of up to this fraction of half the Row Spacing, so the rows are not straight lines. Works with one row too (a rough band along the path). |
| Random Shift Along | 0 to 1: each point is moved along the path by up to this fraction of half the gap between neighbours, so the points of the rows do not line up. |
| Stagger Rows | A slider, 0 to 1 (v1.18.0): every second row is shifted along the path by this fraction of the gap between neighbours. 0 is off, **0.5 a brick pattern**, 1 a full gap. (Before v1.18.0 it was a tick that meant 0.5.) |
| Rows Seed | Seed of the random numbers. |

**Ids.** Row 0 keeps the ids of the path; row k gets `id + k * 20,000,000`. A point's random offsets are keyed on its id, so **adding or removing rows never moves or renames the points that stay** (use *Centre The Rows* off when you want the first rows to stay in place as you add more).

**Where it runs.** Right after the Distribution Mode, before the Mask, the Field Stack, the Falloff and the Variation, so all of them (and Separation, Overrides, Grow, camera optimisation ...) work on every row like on any other point; every attribute of a point (a Circle's facing, the curve number, the path direction) is copied to its copies. The Falloff (Region: whole layout) measures the whole set of rows.

**Directions.** Sideways is horizontal and perpendicular to the path (cross product of up and the path direction), so a Line along Y falls back to X. A Circle uses the radial direction in its own plane (XZ, XY or YZ). A Curve uses the tangent of the curve at each point (the Curve generator now writes it as `pathdir`).

## Evidence and limits

`tests/validate_rows.py` (6 groups, 6 mutations): offsets, directions for every mode and plane, the gap, the expansion, the random and stagger bounds, the stability of a point when rows are added, rows next to each other (centred and on one side), concentric rings with the facing copied, a curve with a bend (offsets along Z on one leg and along X on the next), the previous release reproduced with one row, other modes untouched, the Falloff and the Mask working on all rows. How the section looks on the Layout tab is for the user to judge. Rows are laid out in the ground plane (a Line along Y, or rows above each other, are not offered); a Curve with sharp corners gets the offsets of the segment each point sits on, so rows can cross on the inside of a tight bend.

Demo: `dist/Arraytron_v1.14.0_rows_demo.hip` (render `renders/arraytron_v1.14.0_rows_demo_xpu.png`): a Line in 4 straight rows, in 4 loose rows, in 4 staggered rows, a Circle as 3 rings and a Curve in 3 rows.
