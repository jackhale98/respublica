"""Run every importer: python -m importers"""

from importers import IMPORTERS
from tools.common import ROOT

for module in IMPORTERS:
    for path in module.run():
        print(f"{module.__name__}: wrote {path.relative_to(ROOT)}")
