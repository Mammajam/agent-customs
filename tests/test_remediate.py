import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from customs import Ecosystem
from customs.checkpoint import check_command
from customs.registry import PackageFacts
from customs.remediate import apply_fix, patch_package_json, patch_requirements, plan_replacements
from customs.typos import closest_popular
from customs.verdict import Verdict

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


class Registry:
    """Known packages come from the table; anything else is absent, with the real typo check."""

    def __init__(self, table):
        self.table = table

    def inspect(self, ecosystem, name, version=None):
        if name in self.table:
            return self.table[name]
        match, distance = closest_popular(name, ecosystem.value)
        return PackageFacts(ecosystem, name, exists=False, typo_of=match, typo_distance=distance)


GOOD = PackageFacts(Ecosystem.PYPI, "requests", exists=True,
                    first_published=NOW - timedelta(days=900), maintainers=2)
REGISTRY = Registry({"requests": GOOD})


class PatchTests(unittest.TestCase):
    def test_requirements_replaces_name_and_keeps_specifier(self):
        text = "flask==3.0.0\nreqeusts>=2.31\n# comment\n"
        self.assertEqual(patch_requirements(text, {"reqeusts": "requests"}),
                         "flask==3.0.0\nrequests>=2.31\n# comment\n")

    def test_requirements_does_not_touch_similar_names(self):
        text = "reqeusts-extra==1\n"
        self.assertEqual(patch_requirements(text, {"reqeusts": "requests"}), text)

    def test_package_json_renames_dependency(self):
        text = json.dumps({"dependencies": {"lodsh": "^4.0.0"}, "devDependencies": {}})
        out = json.loads(patch_package_json(text, {"lodsh": "lodash"}))
        self.assertEqual(out["dependencies"], {"lodash": "^4.0.0"})


class PlanTests(unittest.TestCase):
    def test_suggestion_that_checks_clean_is_used(self):
        decisions = check_command("pip install reqeusts", REGISTRY, NOW)
        replacements, notes = plan_replacements(decisions, REGISTRY)
        self.assertEqual(replacements, {"reqeusts": "requests"})
        self.assertEqual(notes, [])


class PinnedFixTests(unittest.TestCase):
    def test_vulnerable_pin_is_not_carried_over(self):
        vulnerable = PackageFacts(Ecosystem.PYPI, "requests", exists=True,
                                  first_published=NOW - timedelta(days=900), maintainers=2,
                                  vulnerability_ids=["GHSA-x"])
        reg = Registry({"requests": vulnerable})
        decisions = check_command("pip install reqeusts==2.5.0", reg, NOW)
        replacements, notes = plan_replacements(decisions, reg, NOW)
        self.assertEqual(replacements, {})
        self.assertIn("not clean", notes[0])


class ApplyFixTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.manifest = self.dir / "requirements.txt"
        self.manifest.write_text("reqeusts==2.31.0\n")
        self.decisions = check_command("pip install reqeusts", REGISTRY, NOW)

    def test_passing_tests_keep_the_fix(self):
        result = apply_fix(self.manifest, self.decisions, f"{sys.executable} -c 'exit(0)'",
                           registry=REGISTRY, cwd=self.dir)
        self.assertEqual(result.status, "fixed")
        self.assertEqual(self.manifest.read_text(), "requests==2.31.0\n")

    def test_failing_tests_restore_the_original(self):
        result = apply_fix(self.manifest, self.decisions, f"{sys.executable} -c 'exit(1)'",
                           registry=REGISTRY, cwd=self.dir)
        self.assertEqual(result.status, "tests-failed")
        self.assertEqual(self.manifest.read_text(), "reqeusts==2.31.0\n")

    def test_nothing_to_fix_leaves_file_alone(self):
        clean = check_command("pip install requests", REGISTRY, NOW)
        result = apply_fix(self.manifest, clean, "false", registry=REGISTRY, cwd=self.dir)
        self.assertEqual(result.status, "nothing to fix")
        self.assertEqual(self.manifest.read_text(), "reqeusts==2.31.0\n")




class ManifestInstallTests(unittest.TestCase):
    def test_every_requirement_is_checked(self):
        from customs.cli import manifest_installs
        d = Path(tempfile.mkdtemp())
        f = d / "requirements.txt"
        f.write_text("# deps\nflask==3.0.0\nreqeusts==2.31.0\n\n")
        decisions = check_command(manifest_installs(f), REGISTRY, NOW)
        names = [x.declaration.name for x in decisions]
        self.assertEqual(names, ["flask", "reqeusts"])

    def test_package_json_names_are_checked(self):
        from customs.cli import manifest_installs
        d = Path(tempfile.mkdtemp())
        f = d / "package.json"
        f.write_text(json.dumps({"dependencies": {"lodash": "^4"}, "devDependencies": {"jest": "^29"}}))
        self.assertEqual(manifest_installs(f), "npm install lodash && npm install jest")


if __name__ == "__main__":
    unittest.main()
