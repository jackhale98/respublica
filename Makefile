# Res Publica pipeline: fetch -> import -> verify -> build
# Python tools use only the standard library; the site needs Node (see site/package.json).

PYTHON ?= python3
NPM ?= npm

.PHONY: help fetch import verify test lock-refs site-data build dev clean

help:
	@echo "make fetch      restore raw sources listed in sources/manifest.json"
	@echo "make import     run every importer (sources/raw -> texts/)"
	@echo "make verify     run all data checks and unit tests (required before finishing any task)"
	@echo "make lock-refs  add new refs to refs.lock (published refs are permanent)"
	@echo "make build      build the site and its search index into site/dist, then check it"
	@echo "make dev        run the site locally"

fetch:
	$(PYTHON) -m tools.fetch

import:
	$(PYTHON) -m importers

test:
	$(PYTHON) -m unittest discover -s tests -t .

verify: test
	$(PYTHON) -m tools.verify

lock-refs:
	$(PYTHON) -m tools.refs lock

site-data:
	$(PYTHON) -m tools.site_data

site/node_modules: site/package.json site/package-lock.json
	cd site && $(NPM) ci --no-audit --no-fund
	@touch site/node_modules

build: site-data site/node_modules
	cd site && $(NPM) run build
	$(PYTHON) -m tools.search_site
	$(PYTHON) -m tools.check_site

dev: site-data site/node_modules
	cd site && $(NPM) run dev

clean:
	rm -rf site/dist site/.data site/.astro
