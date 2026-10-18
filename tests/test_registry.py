import unittest
from datetime import datetime, timezone

from customs import Ecosystem
from customs.registry import (
    NPM_DOWNLOADS_URL,
    NPM_URL,
    OSV_URL,
    PYPI_URL,
    RegistryClient,
)
from customs.typos import closest_popular, osa_distance


class FakeRegistry:
    """Maps URLs to canned JSON. Unknown URLs behave like a 404."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.responses.get(url)


PYPI_DOC = {
    "info": {"version": "2.31.0", "author": "Kenneth Reitz", "maintainer": None},
    "releases": {
        "2.0.0": [{"upload_time_iso_8601": "2015-01-01T10:00:00.000000Z"}],
        "2.31.0": [{"upload_time_iso_8601": "2023-05-22T12:00:00.000000Z"}],
    },
}


class TypoTests(unittest.TestCase):
    def test_osa_counts_transposition_as_one(self):
        self.assertEqual(osa_distance("reqeusts", "requests"), 1)

    def test_osa_basic_cases(self):
        self.assertEqual(osa_distance("kitten", "sitting"), 3)
        self.assertEqual(osa_distance("", "abc"), 3)

    def test_near_miss_of_popular_name(self):
        self.assertEqual(closest_popular("reqeusts", "pypi"), ("requests", 1))

    def test_popular_name_is_not_a_typo(self):
        self.assertEqual(closest_popular("requests", "pypi"), (None, None))

    def test_distant_name_is_not_flagged(self):
        self.assertEqual(closest_popular("react-codeshift", "npm"), (None, None))

    def test_ecosystems_are_separate(self):
        self.assertEqual(closest_popular("pandsa", "pypi"), ("pandas", 1))
        self.assertEqual(closest_popular("pandsa", "npm"), (None, None))


class RegistryTests(unittest.TestCase):
    def test_pypi_existing_package(self):
        fake = FakeRegistry({
            PYPI_URL.format(name="requests"): PYPI_DOC,
            OSV_URL: {"vulns": [{"id": "GHSA-xxxx"}]},
        })
        facts = RegistryClient(fake).inspect(Ecosystem.PYPI, "requests")
        self.assertTrue(facts.exists)
        self.assertEqual(facts.latest_version, "2.31.0")
        self.assertEqual(facts.first_published, datetime(2015, 1, 1, 10, tzinfo=timezone.utc))
        self.assertEqual(facts.maintainers, 1)
        self.assertEqual(facts.vulnerability_ids, ["GHSA-xxxx"])
        self.assertIsNone(facts.typo_of)

    def test_pypi_missing_package_skips_osv(self):
        fake = FakeRegistry({})
        facts = RegistryClient(fake).inspect(Ecosystem.PYPI, "no-such-pkg-zz9")
        self.assertFalse(facts.exists)
        self.assertEqual(facts.vulnerability_ids, [])
        self.assertEqual(len(fake.calls), 1)

    def test_pypi_typo_flagged_for_nonexistent_near_miss(self):
        facts = RegistryClient(FakeRegistry({})).inspect(Ecosystem.PYPI, "reqeusts")
        self.assertEqual((facts.typo_of, facts.typo_distance), ("requests", 1))

    def test_npm_package_with_downloads_and_maintainers(self):
        npm_doc = {
            "time": {"created": "2014-03-01T00:00:00.000Z"},
            "dist-tags": {"latest": "1.3.0"},
            "maintainers": [{"name": "a"}, {"name": "b"}],
        }
        fake = FakeRegistry({
            NPM_URL.format(name="lodash"): npm_doc,
            NPM_DOWNLOADS_URL.format(name="lodash"): {"downloads": 12345},
            OSV_URL: {},
        })
        facts = RegistryClient(fake).inspect(Ecosystem.NPM, "lodash")
        self.assertEqual(facts.weekly_downloads, 12345)
        self.assertEqual(facts.maintainers, 2)
        self.assertEqual(facts.latest_version, "1.3.0")
        self.assertEqual(facts.vulnerability_ids, [])

    def test_npm_scoped_name_is_quoted_keeping_at_sign(self):
        fake = FakeRegistry({})
        RegistryClient(fake).inspect(Ecosystem.NPM, "@scope/tool")
        self.assertEqual(fake.calls[0][0], "https://registry.npmjs.org/@scope%2Ftool")

    def test_unsupported_ecosystem_raises(self):
        with self.assertRaises(ValueError):
            RegistryClient(FakeRegistry({})).inspect(Ecosystem.GIT, "github.com/a/b")


if __name__ == "__main__":
    unittest.main()
