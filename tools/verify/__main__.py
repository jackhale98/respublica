"""python -m tools.verify — run every check; exit non-zero on any failure."""

import sys

from tools.verify import run_all

results = run_all()
failed = 0
for name, errors in results.items():
    status = "ok" if not errors else f"{len(errors)} error(s)"
    print(f"[{name}] {status}")
    for e in errors[:200]:
        print(f"  - {e}")
    if len(errors) > 200:
        print(f"  ... and {len(errors) - 200} more")
    failed += len(errors)
sys.exit(1 if failed else 0)
