"""python -m tools.verify — run every check; exit non-zero on any failure.

    python -m tools.verify                      # everything (make verify; CI on main)
    python -m tools.verify --importers a,b      # re-run only these importers for the
                                                # reproducibility check (decision 65);
                                                # "" runs none
"""

import argparse
import sys

import tools.verify as verify

ap = argparse.ArgumentParser(prog="python -m tools.verify")
ap.add_argument("--importers", help="comma-separated importers for the reproducibility check")
args = ap.parse_args()
if args.importers is not None:
    verify.ONLY_IMPORTERS = [n for n in args.importers.split(",") if n]
results = verify.run_all()
failed = 0
for name, errors in results.items():
    status = "ok" if not errors else f"{len(errors)} error(s)"
    if name == "reproducible" and verify.ONLY_IMPORTERS is not None and not errors:
        status = f"ok (only: {', '.join(verify.ONLY_IMPORTERS) or 'none'}; the full check runs on main)"
    print(f"[{name}] {status}")
    for e in errors[:200]:
        print(f"  - {e}")
    if len(errors) > 200:
        print(f"  ... and {len(errors) - 200} more")
    failed += len(errors)
sys.exit(1 if failed else 0)
