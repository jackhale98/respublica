"""Importers: one module per upstream source. Each exposes run(out_dir) -> [paths]
and writes to texts/ unless it sets OUT_DIR (cases/ for the case import)."""

from importers import annals, cases, elliot, federalist, globe, nara, pamphlets, ratification, record

IMPORTERS = [nara, federalist, ratification, pamphlets, elliot, annals, globe, record, cases]
