#!/bin/bash
# Build every Houdini 20.5 / 21 HDA (the v1.1.0 release build and the older baselines the suites compare against) with hython 20.5.
# Usage: bash tools/build_h205_all.sh [hython.exe]      Never run while a suite is executing (they load these files).
H="${1:-/c/Program Files/Side Effects Software/Houdini 20.5.445/bin/hython.exe}"
for v in v0.3.0 v0.3.5 v0.3.6 v0.4.0 v0.4.5 v0.4.6 v0.5.0 v0.5.1 v0.5.2 v0.6.0 v0.7.0 v0.8.0 v0.9.0 v1.0.0 v1.1.0 v1.5.0 v1.6.0; do
  echo "$v: $("$H" tools/build_arraytron_v03.py $v 2>&1 | grep -c '"errors": \[\]') ok"
done
rm -rf otls_h205/backup                                   # Houdini keeps a backup of every overwritten HDA
mkdir -p otls_h205/test_assets && cp -r dist/test_assets/. otls_h205/test_assets/     # the demo scenes reference $HIP/test_assets
