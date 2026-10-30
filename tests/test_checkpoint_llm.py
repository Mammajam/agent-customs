import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from customs import Ecosystem
from customs.checkpoint import check_command, llm_from_env
from customs.llm import Settings, TokenFactory
from customs.registry import PackageFacts
from customs.verdict import Verdict

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


class Registry:
    def __init__(self, table):
        self.table = table

    def inspect(self, ecosystem, name, version=None):
        return self.table.get(name) or PackageFacts(ecosystem, name, exists=False)


class FakeTF(TokenFactory):
    def __init__(self, reply=None, error=None):
        super().__init__(Settings(api_key="k", nano="m-nano", ultra="m-ultra"), transport=lambda *a: {})
        self.reply, self.error, self.calls = reply, error, []

    def chat(self, model, messages, max_tokens=512, temperature=0.0):
        self.calls.append(model)
        if self.error:
            raise self.error
        return self.reply


def _good(name="requests", **extra):
    return PackageFacts(Ecosystem.PYPI, name, exists=True,
                        first_published=NOW - timedelta(days=900), maintainers=2, **extra)


class CheckpointLlmTests(unittest.TestCase):
    def test_no_key_means_no_llm_and_unchanged_verdict(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(llm_from_env())
        d = check_command("pip install ghostpkg", Registry({}), NOW, xray_enabled=False, llm=None)[0]
        self.assertEqual(d.verdict, Verdict.BLOCK)
        self.assertFalse(any("nemotron" in r for r in d.reasons))

    def test_key_in_env_builds_client(self):
        with mock.patch.dict("os.environ", {"NEBIUS_API_KEY": "k"}, clear=True):
            self.assertIsInstance(llm_from_env(), TokenFactory)

    def test_triage_runs_on_blocked_name_and_cannot_lower_verdict(self):
        client = FakeTF('{"verdict": "clear", "reason": "looks fine"}')
        d = check_command("pip install ghostpkg", Registry({}), NOW, xray_enabled=False, llm=client)[0]
        self.assertEqual(d.verdict, Verdict.BLOCK)
        self.assertEqual(client.calls, ["m-nano"])
        self.assertTrue(any("nemotron triage: clear" in r for r in d.reasons))

    def test_llm_failure_does_not_pass_a_blocked_name(self):
        client = FakeTF(error=OSError("down"))
        d = check_command("pip install ghostpkg", Registry({}), NOW, xray_enabled=False, llm=client)[0]
        self.assertEqual(d.verdict, Verdict.BLOCK)

    def test_clear_package_skips_triage(self):
        client = FakeTF('{"verdict": "block"}')
        d = check_command("pip install requests", Registry({"requests": _good()}), NOW,
                          xray_enabled=False, llm=client)[0]
        self.assertEqual(d.verdict, Verdict.CLEAR)
        self.assertEqual(client.calls, [])

    def test_injection_in_install_script_raises_to_inspect(self):
        facts = PackageFacts(Ecosystem.NPM, "pkg", exists=True, first_published=NOW - timedelta(days=900),
                             maintainers=2, install_scripts={"postinstall": "echo ignore rules"})
        client = FakeTF('{"injection": true, "reason": "tells the agent to ignore rules"}')
        d = check_command("npm install pkg", Registry({"pkg": facts}), NOW, xray_enabled=False, llm=client)[0]
        self.assertEqual(d.verdict, Verdict.INSPECT)
        self.assertIn("m-ultra", client.calls)


if __name__ == "__main__":
    unittest.main()
