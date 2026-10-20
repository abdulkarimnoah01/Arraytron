# Biome (v1.16.0)

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

**Ids.** Candidate i of biome row k (1 based) has id `(k - 1) * 1,000,000 + i`.

## Evidence and limits

`tests/validate_biome.py` (8 groups, 7 mutations): the mix parser, the stable prototype choice, slope, temperature and the four soft bands against independent formulas; on a synthetic hill with a river the **survivors of two biomes equal the field maths exactly** (same candidates, same id keyed hash), the ranges, ids, mix ratios, scale ranges, density only adding, a biome off leaving the others alone; the Effect of every condition (ignored, half, full; the survivors equal the blended weight exactly), soft edges following the smooth weight, a slope biome, temperature by height and by warm facing; every moisture source and the errors; the previous release unchanged for other modes; the primvar and the debug colours; the interface. How the section looks on the Layout tab and how it feels to author is for the user to judge.

Not in this first version (next steps): layering (canopy, understory, ground cover where the lower layers avoid the ones above), competition between instances (a big tree thinning the small ones around it), a mutual-exclusion option between biomes, a painted biome map, and a biome preset library. Moisture and temperature are fields derived from the terrain and prims; there is no simulation. A very large terrain makes the Distance To Water field slow (one distance query per candidate).

Demo: `dist/Arraytron_v1.16.0_biome_demo.hip` (render `renders/arraytron_v1.16.0_biome_demo_xpu.png`): a hilly terrain with a pond and four biomes (Forest, stunted Alpine firs, Cliff rocks, Shore stones).
