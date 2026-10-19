import io
import json
import unittest
from datetime import datetime, timedelta, timezone

from customs import Ecosystem, parse_command
from customs.checkpoint import check_command, overall
from customs.hook import handle, run
from customs.parser import Declaration
from customs.registry import PackageFacts
from customs.verdict import Verdict, judge

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def facts(**kw):
    base = dict(ecosystem=Ecosystem.PYPI, name="pkg", exists=True,
                first_published=NOW - timedelta(days=900), maintainers=2)
    base.update(kw)
    return PackageFacts(**base)


def decl(eco=Ecosystem.PYPI, name="pkg"):
    return Declaration(eco, name)


class FakeRegistry:
    def __init__(self, table):
        self.table = table

    def inspect(self, ecosystem, name, version=None):
        if name not in self.table:
            return PackageFacts(ecosystem, name, exists=False)
        return self.table[name]


class BrokenRegistry:
    def inspect(self, ecosystem, name, version=None):
        raise OSError("network down")


class JudgeTests(unittest.TestCase):
    def test_established_package_is_clear(self):
        self.assertEqual(judge(decl(), facts(), NOW).verdict, Verdict.CLEAR)

    def test_nonexistent_package_is_blocked(self):
        d = judge(decl(name="ghost"), facts(exists=False, name="ghost"), NOW)
        self.assertEqual(d.verdict, Verdict.BLOCK)

    def test_nonexistent_near_miss_suggests_real_name(self):
        d = judge(decl(name="reqeusts"), facts(exists=False, typo_of="requests", typo_distance=1), NOW)
        self.assertEqual(d.verdict, Verdict.BLOCK)
        self.assertEqual(d.suggestion, "requests")

    def test_young_near_miss_is_blocked(self):
        f = facts(typo_of="requests", typo_distance=1, first_published=NOW - timedelta(days=5))
        self.assertEqual(judge(decl(name="reqeusts"), f, NOW).verdict, Verdict.BLOCK)

    def test_old_near_miss_asks(self):
        f = facts(typo_of="requests", typo_distance=1)
        self.assertEqual(judge(decl(name="reqeusts"), f, NOW).verdict, Verdict.INSPECT)

    def test_new_package_asks(self):
        f = facts(first_published=NOW - timedelta(days=3))
        self.assertEqual(judge(decl(), f, NOW).verdict, Verdict.INSPECT)

    def test_advisories_on_pinned_version_ask(self):
        f = facts(vulnerability_ids=["GHSA-1"])
        d = judge(Declaration(Ecosystem.PYPI, "pkg", specifier="==1.0"), f, NOW)
        self.assertEqual(d.verdict, Verdict.INSPECT)
        self.assertIn("GHSA-1", d.reasons[0])

    def test_advisories_on_unpinned_install_are_noted_not_asked(self):
        f = facts(vulnerability_ids=["GHSA-1", "GHSA-2"])
        d = judge(decl(), f, NOW)
        self.assertEqual(d.verdict, Verdict.CLEAR)
        self.assertIn("2 advisories on past versions", d.reasons)

    def test_unknown_publish_date_asks(self):
        self.assertEqual(judge(decl(), facts(first_published=None), NOW).verdict, Verdict.INSPECT)

    def test_npm_low_downloads_asks(self):
        f = facts(ecosystem=Ecosystem.NPM, weekly_downloads=3)
        self.assertEqual(judge(decl(Ecosystem.NPM), f, NOW).verdict, Verdict.INSPECT)

    def test_npm_unknown_downloads_asks(self):
        f = facts(ecosystem=Ecosystem.NPM, weekly_downloads=None)
        self.assertEqual(judge(decl(Ecosystem.NPM), f, NOW).verdict, Verdict.INSPECT)

    def test_npm_no_maintainer_asks(self):
        f = facts(ecosystem=Ecosystem.NPM, maintainers=0, weekly_downloads=10**6)
        self.assertEqual(judge(decl(Ecosystem.NPM), f, NOW).verdict, Verdict.INSPECT)

    def test_pypi_unknown_maintainers_does_not_ask(self):
        self.assertEqual(judge(decl(), facts(maintainers=None), NOW).verdict, Verdict.CLEAR)


class CheckpointTests(unittest.TestCase):
    def test_hallucinated_install_is_blocked_with_suggestion(self):
        reg = FakeRegistry({"reqeusts": facts(exists=False, typo_of="requests", typo_distance=1)})
        decisions = check_command("pip install reqeusts", reg, NOW)
        self.assertEqual(overall(decisions), Verdict.BLOCK)
        self.assertEqual(decisions[0].suggestion, "requests")

    def test_clean_install_is_clear(self):
        reg = FakeRegistry({"flask": facts(name="flask")})
        self.assertEqual(overall(check_command("pip install flask", reg, NOW)), Verdict.CLEAR)

    def test_git_clone_is_not_passed_silently(self):
        decisions = check_command("git clone https://github.com/a/b", FakeRegistry({}), NOW)
        self.assertEqual(overall(decisions), Verdict.INSPECT)

    def test_registry_failure_asks_instead_of_passing(self):
        decisions = check_command("pip install flask", BrokenRegistry(), NOW)
        self.assertEqual(overall(decisions), Verdict.INSPECT)
        self.assertIn("registry lookup failed", decisions[0].reasons[0])

    def test_unparsed_requirements_file_asks(self):
        decisions = check_command("pip install -r requirements.txt", FakeRegistry({}), NOW)
        self.assertEqual(overall(decisions), Verdict.INSPECT)

    def test_no_install_means_nothing_to_decide(self):
        self.assertEqual(check_command("ls -la", FakeRegistry({}), NOW), [])


class HookTests(unittest.TestCase):
    def payload(self, command, tool="Bash"):
        return {"tool_name": tool, "tool_input": {"command": command}}

    def test_non_bash_tool_is_ignored(self):
        self.assertIsNone(handle(self.payload("pip install x", tool="Read"), FakeRegistry({})))

    def test_clear_command_is_silent(self):
        reg = FakeRegistry({"flask": facts(name="flask")})
        self.assertIsNone(handle(self.payload("pip install flask"), reg))

    def test_block_answers_deny_with_reason(self):
        reg = FakeRegistry({"reqeusts": facts(exists=False, typo_of="requests", typo_distance=1)})
        out = handle(self.payload("pip install reqeusts"), reg)
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertEqual(spec["permissionDecision"], "deny")
        self.assertIn("Did you mean `requests`", spec["permissionDecisionReason"])

    def test_inspect_answers_ask(self):
        out = handle(self.payload("git clone https://github.com/a/b"), FakeRegistry({}))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_run_reads_stdin_and_writes_json(self):
        stdin = io.StringIO(json.dumps(self.payload("git clone https://github.com/a/b")))
        stdout = io.StringIO()
        import customs.hook as hook
        original = hook.check_command
        hook.check_command = lambda cmd, registry=None: original(cmd, FakeRegistry({}), NOW)
        try:
            self.assertEqual(run(stdin, stdout), 0)
        finally:
            hook.check_command = original
        self.assertEqual(json.loads(stdout.getvalue())["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_bad_stdin_fails_safe_to_ask(self):
        stdout = io.StringIO()
        self.assertEqual(run(io.StringIO("not json"), stdout), 0)
        self.assertEqual(json.loads(stdout.getvalue())["hookSpecificOutput"]["permissionDecision"], "ask")


if __name__ == "__main__":
    unittest.main()
