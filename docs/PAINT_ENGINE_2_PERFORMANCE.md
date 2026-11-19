# Paint Engine 2.0: performance (measured)

Measured with `tools/bench_paint_engine.py`: the real viewer-state code of each HDA driven through a stand-in viewport (no GPU drawing is measured), Houdini 22.0.368 hython,
a terrain of 80 000 triangles, brush radius 2, density 3, spacing 0.3, the Soft Natural / default falloff, 201 mouse events per stroke, 120 hover events. Milliseconds per mouse event (mean / 95th percentile);
commit = the release of the stroke (the parameter write); cook = the LOP cook after the stroke. Machine: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel, Windows 11.

Before = Arraytron v1.35.0 and Arraytron Stamp 0.10.0; after = Arraytron v1.36.0 and Arraytron Stamp 0.11.0 (Paint Engine 2.0). Each number is one run on one machine: they vary by a few milliseconds between runs.

## Arraytron (procedural paint)

| Instances | Hover before | Hover after | Paint event before | Paint event after | Paint commit before / after | Erase event before / after | Cook after stroke before / after | Points painted before / after |
|---|---|---|---|---|---|---|---|---|
| 1000 | 6.10 / 7.78 | 1.61 / 2.34 | 18.1 / 20.2 | 2.05 / 2.62 | 8.65 / 5.47 | 7.01 / 0.88 | 17.4 / 41.3 | 693 / 278 |
| 10000 | 5.95 / 7.31 | 1.60 / 2.32 | 23.6 / 38.1 | 2.19 / 2.61 | 20.6 / 22.6 | 13.6 / 1.07 | 31.5 / 32.4 | 535 / 190 |
| 50000 | 5.99 / 7.27 | 1.58 / 2.52 | 18.8 / 22.0 | 2.72 / 2.81 | 74.6 / 91.0 | 39.6 / 1.34 | 71.3 / 101.6 | 0 / 42 |
| 100000 | 5.64 / 7.01 | 1.68 / 2.33 | 19.3 / 21.8 | 2.75 / 2.96 | 144.1 / 161.6 | 82.1 / 1.44 | 127.0 / 180.3 | 0 / 2 |

Sculpt brushes after (mean ms per mouse event / commit ms / undo restores / redo re-applies):

| Instances | Relax | Scale | Push |
|---|---|---|---|
| 1000 | 0.91 / 2.50 / yes / yes | 0.97 / 2.32 / yes / yes | 0.93 / 2.43 / yes / yes |
| 10000 | 1.00 / 19.4 / yes / yes | 1.07 / 19.5 / yes / yes | 1.05 / 27.1 / yes / yes |
| 50000 | 1.13 / 80.4 / yes / yes | 1.09 / 81.3 / yes / yes | 1.08 / 118.8 / yes / yes |
| 100000 | 1.43 / 151.7 / yes / yes | 1.17 / 190.8 / yes / yes | 1.18 / 157.0 / yes / yes |

Paint stroke undo / redo after: 1000: undo 1.12 ms (restores), redo 0.69 ms (re-applies), peak Python memory of the stroke 0.62 MB; 10000: undo 6.65 ms (restores), redo 6.47 ms (re-applies), peak Python memory of the stroke 3.56 MB; 50000: undo 38.9 ms (restores), redo 31.0 ms (re-applies), peak Python memory of the stroke 10.42 MB; 100000: undo 62.8 ms (restores), redo 61.0 ms (re-applies), peak Python memory of the stroke 19.11 MB

Save / reopen after: 1000: save 130.1 ms, reopen + cook 1087.9 ms (same count); 10000: save 94.7 ms, reopen + cook 392.2 ms (same count); 50000: save 173.5 ms, reopen + cook 465.2 ms (same count); 100000: save 215.5 ms, reopen + cook 614.4 ms (same count)

## Arraytron Stamp (stamps)

| Instances | Hover before | Hover after | Paint event before | Paint event after | Paint commit before / after | Erase event before / after | Cook after stroke before / after | Points painted before / after |
|---|---|---|---|---|---|---|---|---|
| 1000 | 6.44 / 6.99 | 1.79 / 1.98 | 7.97 / 10.1 | 2.65 / 3.61 | 11.5 / 8.38 | 5.84 / 1.08 | 8.57 / 34.6 | 278 / 278 |
| 10000 | 9.13 / 9.94 | 3.21 / 5.41 | 10.2 / 16.4 | 3.60 / 6.70 | 16.6 / 9.70 | 12.1 / 2.07 | 51.6 / 51.6 | 188 / 188 |
| 50000 | 17.3 / 22.0 | 6.95 / 7.78 | 19.4 / 37.9 | 9.16 / 26.7 | 36.8 / 27.7 | 40.6 / 7.47 | 254.5 / 280.9 | 32 / 32 |
| 100000 | 29.0 / 33.0 | 14.8 / 15.9 | 33.4 / 38.6 | 14.6 / 14.7 | 28.1 / 15.2 | 73.1 / 14.3 | 548.7 / 585.1 | 5 / 5 |

Sculpt brushes after (mean ms per mouse event / commit ms / undo restores / redo re-applies):

| Instances | Relax | Scale | Push |
|---|---|---|---|
| 1000 | 1.01 / 0.96 / yes / yes | 1.00 / 1.16 / yes / yes | 0.99 / 0.92 / yes / yes |
| 10000 | 2.29 / 2.75 / yes / yes | 2.01 / 2.14 / yes / yes | 1.92 / 1.99 / yes / yes |
| 50000 | 6.21 / 9.25 / yes / yes | 6.87 / 6.82 / yes / yes | 5.88 / 6.72 / yes / yes |
| 100000 | 17.1 / 12.4 / yes / yes | 16.9 / 11.8 / yes / yes | 16.8 / 11.3 / yes / yes |

Paint stroke undo / redo after: 1000: undo 2.82 ms (restores), redo 2.43 ms (re-applies), peak Python memory of the stroke 0.69 MB; 10000: undo 20.6 ms (restores), redo 17.9 ms (re-applies), peak Python memory of the stroke 3.15 MB; 50000: undo 93.1 ms (restores), redo 90.3 ms (re-applies), peak Python memory of the stroke 11.31 MB; 100000: undo 196.6 ms (restores), redo 172.0 ms (re-applies), peak Python memory of the stroke 22.58 MB

Save / reopen after: 1000: save 97.6 ms, reopen + cook 341.6 ms (same count); 10000: save 146.0 ms, reopen + cook 243.5 ms (same count); 50000: save 230.3 ms, reopen + cook 425.2 ms (same count); 100000: save 317.1 ms, reopen + cook 715.0 ms (same count)

## What changed, and where the time went

* **Hover (cursor only).** Before: Arraytron tested every triangle of the Paint Target with numpy on every mouse move; Stamp cast 65 rays for the ring and read the HUD values. After: one hou.Geometry ray cast (Houdini's own acceleration structure) for the hit; the ring is cast once per point; the HUD is written only when a value changes. *Python execution and surface queries.*
* **Paint events.** Before: Arraytron made a dab per mouse event (density depended on the event rate), checked the spacing with a Python loop against every point near the dab and redrew every painted point as a new hou.Geometry; Stamp's swept field was already incremental. After: BrushCore's swept field in both, a hash grid for the spacing (only the instances under the brush cost anything), the preview redrawn at most every 60 ms and at most 20 000 dots (a fixed subset by id) plus the stroke. *Python execution, spatial queries, drawing.*
* **Commit.** One parameter write on release (Arraytron) or held-back writes (Stamp): the cost is the length of the data, which is why Arraytron writes once. *Parameter write / serialization.*
* **Limit.** Arraytron v1.35.0 stopped painting at 20 000 painted points (PAINT_MAX); v1.36.0 paints up to 200 000.
