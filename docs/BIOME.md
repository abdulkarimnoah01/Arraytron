# Biome (v1.19.0)

Distribution Mode **Biome** (Layout tab) scatters on a **terrain** by rules: a **table of biomes**, every row with the conditions where it grows (**elevation, slope, moisture, temperature**, each a range with a soft edge), its own **density**, its own **Prototype Mix** and **scale range**. The biomes blend at their borders (an *ecotone*) instead of ending on a hard line, and every point keeps a stable id.

## How a point is decided

Every biome scatters its **own stable candidates** over the whole terrain (the Surface Scatter sampler: the same position for the same candidate number whatever the density is). A candidate survives with the probability of its biome's **weight** at that spot: the product of four band weights, each 1 inside the range and falling to 0 over the **edge** outside it (smoothstep; 0 = a hard edge), each blended with 1 by its **Effect** (below). The choice is a hash of the candidate id, so a higher density, a wider edge or a larger range only ever **adds** points, and turning a biome off or changing another biome never moves the rest. Biomes are independent: where two biomes both have weight, both plant there (a rock in a forest), which is what makes the borders mix.

| Field | How it is measured |
| --- | --- |
| Elevation | The height (world Y) of the candidate. |
| Slope | The angle of the terrain normal from up in degrees (flat 0, wall 90, overhang above 90); face or smooth normals. |
| Moisture (0 to 1) | **Constant**, **Noise**, **Distance To Water** (a mesh or curve prim: 1 at the water, falling smoothly to 0 at the *Water Reach*, measured on the ground plane) or an **Image** (grey value, planar from above), plus a *Moisture Variation* noise and a *Moisture Bias*. |
| Temperature (degrees) | *Temperature (base)* at the *Base Height* minus the *Lapse* (degrees per 100 units of height; the real atmosphere loses about 0.65 per 100 m, use more for a small stylised terrain), plus *Temperature Noise*, plus a **warm facing**: slopes facing the *Warm Direction* are warmer by up to *Warm Facing* degrees (sunny and shady hillsides). |

## The Biome section

Terrain (the prim), Seed, Normal, Align To Normal, Offset, then the Moisture and Temperature settings, a read-out (the points every biome made after the last cook) and the **Biomes** table. One row:

| Column | Meaning |
| --- | --- |
| On, Name | Switch off without deleting; a name for the read-out. |
| Density (per 100 area) | Candidates per 100 square scene units of terrain (at most 100,000 per biome): the density at full weight. |
| Prototype Mix | Prototype Bank row numbers with optional weights: `1 2:3 4:0.5` (row 2 three times as often as row 1, row 4 half as often). A row that is not enabled is ignored (the read-out says so); a mix without any enabled row is an error. |
| Elevation, Slope, Moisture, Temperature + Edge | The four ranges (minimum, maximum) and how far outside them the weight takes to fall to 0. The defaults cover everything, so a biome only needs the conditions you care about. |
| Elevation, Slope, Moisture, Temperature + **Effect** (0 to 1, default 1) | How much that condition counts for this biome. 1 is the band as set; **0 ignores the condition completely** (its weight is 1 everywhere, whatever the range says); in between the condition only partly counts: weight = `1 - effect * (1 - band)`, so a point outside the range still survives with the probability `1 - effect`. |
| Scale Min / Max | A random scale per instance between the two (keyed on its id), multiplied with the Variation and Prototype Bank scales. |

Points carry the biome row (`primvars:biome`, tick **Primvar: biome** on the Optimize tab) and the **Debugging** tab's *Colour Final Points By* has a **Biome** entry (one colour per row). The Mask, Field Stack, Falloff, Separation, Variation, Overrides, Grow, camera optimisation and the rest work on the points like on any other mode (Biome is a world-space mode, like Surface).

**Effect, when prototypes follow different conditions.** A row is one set of conditions. A prototype that follows the elevation but not the temperature gets its **own row** with *Temperature Effect* 0 (and the others at 1); a row can be given the same density and a different Prototype Mix, so the biomes of one terrain stay independent and none moves another. Effects at 1 (the default) reproduce v1.15.0 exactly.

## Layers, Clearance and Exclusion (v1.19.0)

Three more fields end every row of the table: **Layer**, **Clearance** and **Excludes Rows**. They let biomes make room for each other, the way a canopy keeps the ground cover out from under its trunks.

| Field | Meaning |
| --- | --- |
| Layer (1 to 4) | 1 is the top (canopy), bigger numbers are lower (understory, ground cover). A biome on a lower layer keeps clear of the points of the layers above it. Biomes on the same layer do not affect each other, unless one excludes the other. |
| Clearance | The radius around every point of this biome, **multiplied by the point's own scale**, where the biomes below it (and the rows in Excludes Rows) may not put points: the trunk of a tree, the footprint of a bush. 0 (the default) switches the biome's clearing off. |
| Excludes Rows | Row numbers (`2 3`) of biomes that must keep clear of this one **whatever their layer**: a mutual exclusion at borders (a meadow that does not grow under the forest). The distance is this biome's Clearance. This biome is placed before the rows it excludes; if two biomes exclude each other the lower row number wins. Unknown row numbers are ignored. |

How it works: after every biome has made its stable candidates and the conditions have thinned them, the biomes are walked from the top (layer 1) down, a biome after everything that is above it or that excludes it. A point is dropped when it lies closer than Clearance x scale to a surviving point of a biome above it. **Only the biomes above can remove points**, so adding a lower layer, or changing it, never moves a point of the layers above; the ids stay stable; a biome that is off clears nothing. The read-out says how many points each biome lost (*cleared by the layers above*). With every Clearance at 0 the result is exactly v1.18.0.

## Presets (v1.19.0)

**Load Preset...** and **Save Preset...** sit above the Biomes table.

* **Load Preset...** lists four ready-made tables: **Temperate Forest** (canopy trees, understory shrubs, ground cover, cliff rocks), **Alpine** (conifers, stunted trees, meadow plants, scree), **Coastal Wetland** (reeds, shrubs, dune grass, water stones) and **Desert** (scrub, cacti, rocks, dry grass), then your own presets (marked *mine*). It replaces the table (it asks first when the table has rows; one undo step). Every preset row already has its layer and clearance. The Prototype Mix of the k-th row is Prototype Bank row k (or the last row when the bank is shorter): each description names the bank rows it expects.
* **Elevation is fitted to the terrain.** A preset stores elevation as a **fraction of the terrain's height** (0 = lowest point, 1 = highest) and the elevation edge as a fraction of the height range; loading converts them with the height range of the Terrain prim of the node. Slope, moisture and temperature ranges are stored as they are. (Rows with no elevation limit stay open.)
* **Save Preset...** saves the current table under a name (the same name replaces the older preset), elevations as fractions, so it fits other terrains. User presets are one JSON file next to the Asset Library: `biome_presets.json` in `Documents/Arraytron/library`, or in the folder of `ARRAYTRON_LIBRARY`. A broken file is no presets.

**Ids.** Candidate i of biome row k (1 based) has id `(k - 1) * 1,000,000 + i`.

## Evidence and limits

`tests/validate_biome.py` (8 groups, 7 mutations); layers, exclusion and presets in `tests/validate_biomelayers.py` (6 groups, 4 mutations: the survivors against brute-force distances, the upper layer untouched, a third layer, Excludes Rows and its order, every preset loaded and cooked, saving and loading your own, the previous release unchanged): the mix parser, the stable prototype choice, slope, temperature and the four soft bands against independent formulas; on a synthetic hill with a river the **survivors of two biomes equal the field maths exactly** (same candidates, same id keyed hash), the ranges, ids, mix ratios, scale ranges, density only adding, a biome off leaving the others alone; the Effect of every condition (ignored, half, full; the survivors equal the blended weight exactly), soft edges following the smooth weight, a slope biome, temperature by height and by warm facing; every moisture source and the errors; the previous release unchanged for other modes; the primvar and the debug colours; the interface. How the section looks on the Layout tab and how it feels to author is for the user to judge.

Next steps: a painted biome map, and competition between instances of one biome (a big tree thinning the small ones around it; the clearance already keeps the lower layers out). Moisture and temperature are fields derived from the terrain and prims; there is no simulation. A very large terrain makes the Distance To Water field slow (one distance query per candidate).

Demo: `dist/Arraytron_v1.19.0_biome_demo.hip` (render `renders/arraytron_v1.19.0_biome_demo_xpu.png`): a hilly terrain with a pond and four biomes (Forest, stunted Alpine firs, Cliff rocks, Shore stones).
