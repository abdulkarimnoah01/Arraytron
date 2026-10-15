#!/bin/bash
# Run test suites with one Houdini: tools/run_suites.sh <hython.exe> <version> <out dir> suite...   (suite names as in tests/validate_<name>.py)
H="$1"; V="$2"; OUT="$3"; shift 3
mkdir -p "$OUT"
for s in "$@"; do
  "$H" tests/validate_$s.py $V > "$OUT/$s.txt" 2>&1
  echo "$s: $(grep -c '^PASS' "$OUT/$s.txt") pass, $(grep -c -E 'Traceback|AssertionError' "$OUT/$s.txt") fail-markers, last: $(tail -1 "$OUT/$s.txt" | cut -c1-150)"
done
