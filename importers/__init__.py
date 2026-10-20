"""Importers: one module per upstream source. Each exposes run(out_dir) -> [paths]
and writes to texts/ unless it sets OUT_DIR (cases/ for the case import)."""

from importers import annals, cases, elliot, federalist, globe, locke, nara, paine, ratification, record

IMPORTERS = [nara, federalist, ratification, elliot, annals, globe, record, cases, paine, locke]
