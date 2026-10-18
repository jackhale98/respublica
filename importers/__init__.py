"""Importers: one module per upstream source. Each exposes run(out_dir) -> [paths]."""

from importers import annals, federalist, globe, nara, ratification

IMPORTERS = [nara, federalist, ratification, annals, globe]
