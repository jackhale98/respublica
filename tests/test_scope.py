import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from importers import __main__ as runner
from tools import scope

MAP = {
    "ratification": {"outputs": ["texts/brutus.json", "texts/cato.json"], "raw": ["loc-nyjournal-1", "ia-fordx"]},
    "globe": {"outputs": ["texts/house-fourteenth-amendment-1866.json"], "raw": ["ia-globe-1866-pt3-lincoln-txt", "unt-1"]},
    "cases": {"outputs": ["cases/94508.json"], "raw": ["loc-usrep-163-537"]},
}
MANIFEST = [
    {"id": "loc-nyjournal-1", "path": "sources/raw/loc-nyjournal-1.xml"},
    {"id": "ia-fordx", "path": "sources/raw/iaford.txt"},
    {"id": "ia-globe-1866-pt3-lincoln-txt", "path": "sources/raw/ia-globe-1866-pt3-lincoln-txt.txt"},
    {"id": "unt-1", "path": "sources/raw/unt-globe-1.txt"},
    {"id": "loc-usrep-163-537", "path": "sources/raw/loc-usrep-163-537.pdf"},
]


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.patches = [mock.patch.object(scope, "load_map", lambda: MAP),
                        mock.patch.object(scope, "load_manifest", lambda: MANIFEST)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_a_correction_reruns_only_the_importer_of_its_work(self):
        self.assertEqual(scope.importers_for(["brutus"]), ["ratification"])
        self.assertEqual(scope.importers_for(["brutus", "house-fourteenth-amendment-1866"]), ["ratification", "globe"])
        self.assertEqual(scope.importers_for([]), [])

    def test_only_the_cache_families_its_raw_files_are_in(self):
        # loc-nyjournal-* is kept out of git (decision 71); ia-ford here is not a family's name.
        self.assertEqual(scope.families_for(scope.raw_for(["ratification"])), ["nyjournal"])
        self.assertEqual(scope.families_for(scope.raw_for(["globe"])), ["globe"])
        self.assertEqual(scope.families_for(scope.raw_for(["cases", "globe"])), ["globe", "usrep"])

    def test_the_guard_names_changes_outside_the_scope(self):
        with mock.patch.object(scope, "changed", lambda: ["texts/brutus.json", "corrections/brutus.jsonl", "texts/cato.json"]):
            self.assertEqual(scope.main(["--check", "--importers", "ratification", "--allow", "corrections,links"]), 0)
        with mock.patch.object(scope, "changed", lambda: ["texts/brutus.json", "texts/federalist.json"]):
            self.assertEqual(scope.main(["--check", "--importers", "ratification", "--allow", "corrections"]), 1)
        with mock.patch.object(scope, "changed", lambda: ["links/proposed/x.jsonl", "texts/brutus.json"]):
            self.assertEqual(scope.main(["--check", "--allow", "links"]), 1)


class MapTests(unittest.TestCase):
    def test_the_map_is_written_pretty_and_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outputs.json"
            with mock.patch.object(runner, "MAP_PATH", path):
                runner.write_map({"b": {"raw": [], "outputs": ["texts/b.json"]}, "a": {"outputs": [], "raw": ["x"]}})
                self.assertEqual(list(json.loads(path.read_text())), ["a", "b"])
                self.assertEqual(runner.load_map()["b"]["outputs"], ["texts/b.json"])


if __name__ == "__main__":
    unittest.main()
