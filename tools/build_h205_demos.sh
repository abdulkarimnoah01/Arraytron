#!/bin/bash
# Build every demo scene of the Houdini 20.5 / 21 build (otls_h205/Arraytron_<ver>_H205_*demo.hip) with hython 20.5. The HDA is found through the scan path, so the
# scenes do not record an HDA library (see versions.ensure_installed). Run tools/build_h205_all.sh first. Physics demos bake their cache with Bullet 20.5 (minutes).
# Usage: bash tools/build_h205_demos.sh [hython.exe]
cd "$(dirname "$0")/.." || exit 1
H="${1:-/c/Program Files/Side Effects Software/Houdini 20.5.445/bin/hython.exe}"
export HOUDINI_OTLSCAN_PATH="$(pwd -W)/otls_h205;&"
export ARRAYTRON_VERSION="${ARRAYTRON_VERSION:-$(python -c "import sys;sys.path.insert(0,'tools');import versions;print(versions.CURRENT)")}"
for n in v03 paint_v060 paint_k_v150 fields_v070 cluster_v080 camera_v090 finish_v100 imported_v150 lodgen_v180 place_v190 falloff_v1120 rows_v1140 grow_v052 mask_v050 overlap_v051; do
  echo "$n: $("$H" tools/build_demo_$n.py 2>&1 | tail -2 | tr '\n' ' ' | cut -c1-200)"
done
for k in railway box; do echo "physics $k: $("$H" tools/build_demo_physics.py $k 2>&1 | tail -2 | tr '\n' ' ' | cut -c1-250)"; done
echo "all demos: $("$H" tools/build_demo_all.py 2>&1 | grep -v 'Error(\|Warning(' | tail -2 | tr '\n' ' ' | cut -c1-250)"
