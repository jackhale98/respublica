"""Importers: one module per upstream source. Each exposes run(out_dir) -> [paths]."""

from importers import federalist, nara, ratification

IMPORTERS = [nara, federalist, ratification]
