"""Importers: one module per upstream source. Each exposes run(out_dir) -> [paths]
and writes to texts/ unless it sets OUT_DIR (cases/ for the case import)."""

from importers import cases, federalist, nara, ratification

IMPORTERS = [nara, federalist, ratification, cases]
