"""Supreme Court cases from CourtListener (Free Law Project).

    python -m importers.courtlistener lookup    # find each case's cluster (needs COURTLISTENER_TOKEN)
    python -m importers.courtlistener matches   # list the recorded matches

Cases are keyed by CourtListener cluster ID (`Case.{cluster_id}`). The
first set of cases comes from the Constitution Annotated
(`importers.conan.landmark_cases`, decisions 41 to 43), each named by its
U.S. Reports citation ("347 U.S. 483") or, for a slip opinion, its docket
number ("No. 19-1392").

The API allows a token 125 requests a day, so `lookup` asks for few:
CourtListener's citation lookup resolves up to BATCH citations in one
request, and a slip opinion is found by its docket number in the clusters
API. Each response is recorded once as a raw source
(`tools.fetch.add_source`): URL, request body, date, sha256 and license,
and the name of the environment variable holding the token, never the
token. `lookup` asks again only for cases no recorded response matched.
`matches` reads the recorded responses and fails loudly when a case has no
cluster or several, or when the cluster's year is not the year the
Constitution Annotated prints.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass

from tools.common import load_manifest, raw_path, read_json

API = "https://www.courtlistener.com/api/rest/v4/"
SITE = "https://www.courtlistener.com"
TOKEN_ENV = "COURTLISTENER_TOKEN"
LICENSE = ("Free of known copyright restrictions (Public Domain Mark), per CourtListener's "
           "bulk data terms; U.S. court opinions are public domain. Free Law Project.")


class CourtListenerError(ValueError):
    pass


BATCH = 50          # citations per lookup request (the API resolves at most 60 a minute)
BATCH_PAUSE = 65    # seconds between lookup requests
US = re.compile(r"(\d+) U\.S\. (\d+)")
DOCKET = re.compile(r"No\. ([\w-]+)")


def docket_url(key: str) -> str:
    """The clusters API query that finds a slip opinion by its docket number."""
    m = DOCKET.fullmatch(key)
    if not m:
        raise CourtListenerError(f"not a docket number: {key!r}")
    params = [("docket__docket_number", m.group(1)), ("docket__court", "scotus")]
    return f"{API}clusters/?{urllib.parse.urlencode(params)}"


def docket_source(key: str) -> str:
    """Raw source id for a docket lookup: courtlistener-scotus-19-1392."""
    return "courtlistener-scotus-" + re.sub(r"[^a-z0-9-]", "", key.removeprefix("No. ").lower())


def recorded() -> list[tuple[str, object]]:
    """(source id, parsed response) for every recorded CourtListener lookup."""
    return [(e["id"], read_json(raw_path(e["id"]))) for e in load_manifest()
            if e["id"].startswith("courtlistener-")]


@dataclass
class Match:
    key: str            # citation key, as importers.conan gives it
    name: str           # case as the Constitution Annotated prints it
    source_id: str      # the recorded response that gives the cluster
    cluster: dict       # the cluster, as CourtListener's API gives it


def printed_year(name: str) -> str | None:
    """The year in a Constitution Annotated citation: "(1954)", "(U.S. June 24, 2022)"."""
    m = re.search(r"\((?:[^()]*\s)?(\d{4})\)\s*$", name)
    return m.group(1) if m else None


def clusters_for(key: str, responses: list[tuple[str, object]]) -> tuple[str, list[dict]] | None:
    """The clusters a recorded response gives for a case, and that
    response's source id; None if no response answered for it."""
    if US.fullmatch(key):
        for sid, data in responses:
            if not sid.startswith("courtlistener-citations-"):
                continue
            for r in data:
                if key in r.get("normalized_citations", []) and r.get("status") in (200, 300, 404):
                    return sid, r.get("clusters", [])
        return None
    for sid, data in responses:
        if sid == docket_source(key):
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise CourtListenerError(f"{sid}: not a clusters API response: {str(data)[:200]}")
            if data.get("next"):
                raise CourtListenerError(f"{sid}: more than one page of clusters")
            return sid, data["results"]
    return None


def match(key: str, name: str, responses: list[tuple[str, object]]) -> Match:
    """The one cluster CourtListener gives for a case; fails loudly otherwise."""
    found = clusters_for(key, responses)
    if found is None:
        raise CourtListenerError(f"{key} ({name}): not looked up yet")
    sid, clusters = found
    if len(clusters) != 1:
        listed = ", ".join(f"{c.get('id')} {c.get('case_name')!r}" for c in clusters) or "none"
        raise CourtListenerError(f"{key} ({name}): expected one cluster, found {listed} ({sid})")
    cluster = clusters[0]
    year = printed_year(name)
    if year and not str(cluster.get("date_filed", "")).startswith(year):
        raise CourtListenerError(f"{key} ({name}): cluster {cluster.get('id')} is dated {cluster.get('date_filed')}")
    return Match(key, name, sid, cluster)


def landmarks() -> dict[str, str]:
    """Citation key -> name as printed, for the first set of cases."""
    from importers.conan import first_set
    chosen = first_set()
    return {k: c.name for k, c in sorted(chosen.items())}


def cmd_lookup(_: argparse.Namespace) -> int:
    from tools.fetch import add_source
    cases = landmarks()
    responses = recorded()
    todo = [k for k in cases if clusters_for(k, responses) is None]
    cites = [k for k in todo if US.fullmatch(k)]
    dockets = [k for k in todo if not US.fullmatch(k)]
    print(f"{len(cases)} cases; to look up: {len(cites)} citations, {len(dockets)} docket numbers")
    n = sum(1 for sid, _ in responses if sid.startswith("courtlistener-citations-"))
    for i in range(0, len(cites), BATCH):
        if i:
            time.sleep(BATCH_PAUSE)
        n += 1
        batch = cites[i:i + BATCH]
        e = add_source(f"courtlistener-citations-{n}", f"{API}citation-lookup/", LICENSE, ext=".json",
                       auth_env=TOKEN_ENV, post=urllib.parse.urlencode({"text": "; ".join(batch)}),
                       notes=f"CourtListener citation lookup: the clusters for {len(batch)} U.S. Reports "
                             "citations of the first set of cases (decisions 41 to 43).")
        print(f"looked up {len(batch)} citations: {e['path']}", flush=True)
    for key in dockets:
        e = add_source(docket_source(key), docket_url(key), LICENSE, ext=".json", auth_env=TOKEN_ENV,
                       notes=f"CourtListener clusters API: the cluster for {cases[key]} (a slip opinion "
                             "in the Constitution Annotated), by docket number.")
        print(f"looked up {key}: {e['path']}", flush=True)
    return cmd_matches(_, cases)


def cmd_matches(_: argparse.Namespace, cases: dict[str, str] | None = None) -> int:
    cases = cases or landmarks()
    responses = recorded()
    failed = 0
    for key, name in cases.items():
        try:
            c = match(key, name, responses).cluster
        except CourtListenerError as err:
            print(f"error: {err}", file=sys.stderr)
            failed += 1
            continue
        print(f"Case.{c['id']}  {c['case_name']} ({c['date_filed']})  <- {name}")
    print(f"{len(cases) - failed} matched, {failed} failed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m importers.courtlistener")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lookup", help="record each case's cluster from CourtListener (needs the token)")
    sub.add_parser("matches", help="list the recorded matches; fail on none, several or a wrong year")
    args = ap.parse_args(argv)
    return {"lookup": cmd_lookup, "matches": cmd_matches}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
