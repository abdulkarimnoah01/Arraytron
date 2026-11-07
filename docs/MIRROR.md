# Mirror (v1.34.0)

The **Mirror** tab (after Variation) mirrors the finished scatter. It works on the instances that are really there (the Mask, Field Stack, Falloff, variation, Separation, Physics, Blast and the Override Database are done first) and runs before Grow, so it works with every distribution mode and Grow reveals the mirrored half too.

## Use it
1. Switch **Mirror** on.
2. Fill the list **Mirror Operations**. Each row is one operation and works on everything the rows above it made, so two planes make four copies of the scatter, three make eight, and any number of rows works (five give 32).
3. Look at the read-only line below the list: how many instances became how many.

## An operation
| Parameter | What it does |
| --- | --- |
| Enable | Leaves the row out without deleting it. |
| Type | Plane X (the YZ plane), Plane Y (the XZ plane), Plane Z (the XY plane), Custom Plane, or Radial. |
| Center | A point on the plane, or the point the radial axis goes through (the space the instances are generated in, before the Bounds Transform). Move it to mirror about an edge of the scatter. |
| Normal | Custom Plane: the way the plane faces. Radial with Axis Custom: the axis. |
| Axis | Radial: X, Y, Z or Custom. |
| Count | Radial: how many copies of the scatter (the original included). |
| Angle Span | Radial: the angle the copies are spread over; 360 is a full circle, a smaller angle is a fan. |
| Mirror Each Slice | Radial: a mirror image next to every copy (a kaleidoscope, twice as many copies). |
| Mirror Plane Angle | Turns the mirror planes of the kaleidoscope slices about the axis. |
| Mirror The Instances Too | On: a true mirror image of every instance (negative scale and a half turn). Off: only the place and the turning are mirrored; every instance keeps its own handedness (for things that must not be flipped). |
| Keep Original | Off: the scatter is replaced by its mirror image (a flip). |

**Max Instances** (Mirror Safety) stops any operation that would make more instances than that.

## Ids
The originals keep their ids. A copy has `id + stride * copy number`, the stride being the next power of two over the biggest id and at least 2^20, so copies keep the same id on every cook (the Override Database edits the originals; it runs before Mirror).

## Not done
There are no viewport guides for the planes or axes yet, and the copies are exact repeats (same prototype and variation as the original): a different random variation per copy is not offered.

Tests: `tests/validate_mirror.py` (8 groups). Demo: `Arraytron_v1.34.0_mirror_demo.hip`.
