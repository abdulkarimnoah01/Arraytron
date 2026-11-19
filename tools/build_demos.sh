#!/bin/bash
# Build every demo scene of the current release with Houdini 22 (dist/Arraytron_<ver>_*demo.hip), then the all-demos scene. The single scenes stay in the dev tree (the suites use them);
# the release package carries only the all-demos scene. Physics demos bake their cache (minutes). Usage: bash tools/build_demos.sh [hython.exe]
cd "$(dirname "$0")/.." || exit 1
H="${1:-/c/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe}"
for n in v03 paint_v060 paint_k_v150 fields_v070 cluster_v080 camera_v090 finish_v100 imported_v150 lodgen_v180 place_v190 falloff_v1120 rows_v1140 noise_v1220 proxy_v1240 viz_v1240 noisetypes_v1240 masknoise_v1250 palettes_v1250 biome_v1150 grow_v052 mask_v050 overlap_v051 groundauto_v1252 maskpaint_v1260 maskfull_v1270 hpaint_v1280 groups_v1290 surfdir_v1300 surfproxy_v1310 maskshape_v1320 maskfade_v1320 fieldmask_v1330 blast_v1330 mirror_v1340 edit_v1350 lookdev_v1350 matedit_v1350 paintengine_v1360; do
  echo "$n: $("$H" tools/build_demo_$n.py 2>&1 | tail -2 | tr '\n' ' ' | cut -c1-200)"
done
for k in railway box; do echo "physics $k: $("$H" tools/build_demo_physics.py $k 2>&1 | tail -2 | tr '\n' ' ' | cut -c1-250)"; done
echo "all demos: $("$H" tools/build_demo_all.py 2>&1 | grep -v 'Error(\|Warning(' | tail -2 | tr '\n' ' ' | cut -c1-250)"
