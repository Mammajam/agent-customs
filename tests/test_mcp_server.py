import io
import json
import unittest
from unittest import mock

from customs import mcp_server
from customs.parser import Declaration, Ecosystem
from customs.verdict import Decision, Verdict


def call(message):
    return mcp_server.handle(message)


class ProtocolTests(unittest.TestCase):
    def test_initialize_reports_tools_capability(self):
        resp = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(resp["id"], 1)
        self.assertIn("tools", resp["result"]["capabilities"])
        self.assertEqual(resp["result"]["serverInfo"]["name"], "customs")

    def test_notifications_get_no_reply(self):
        self.assertIsNone(call({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list_exposes_check(self):
        resp = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual([t["name"] for t in resp["result"]["tools"]], ["customs.check"])

    def test_unknown_method_is_an_error(self):
        resp = call({"jsonrpc": "2.0", "id": 3, "method": "nope"})
        self.assertEqual(resp["error"]["code"], -32601)

    def test_unknown_tool_is_an_error(self):
        resp = call({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                     "params": {"name": "other", "arguments": {}}})
        self.assertEqual(resp["error"]["code"], -32602)

    def test_missing_command_is_an_error(self):
        resp = call({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                     "params": {"name": "customs.check", "arguments": {}}})
        self.assertEqual(resp["error"]["code"], -32602)


class CheckToolTests(unittest.TestCase):
    def test_block_result_carries_suggestion(self):
        decision = Decision(Declaration(Ecosystem.PYPI, "reqeusts"), Verdict.BLOCK,
                            ["reqeusts does not exist on pypi"], suggestion="requests")
        with mock.patch.object(mcp_server, "check_command", return_value=[decision]):
            resp = call({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                         "params": {"name": "customs.check", "arguments": {"command": "pip install reqeusts"}}})
        content = resp["result"]["content"][0]["text"]
        self.assertIn("BLOCK pypi reqeusts", content)
        self.assertIn("did you mean: requests", content)
        self.assertEqual(resp["result"]["structuredContent"]["overall"], "block")

    def test_checkpoint_failure_asks_rather_than_passes(self):
        with mock.patch.object(mcp_server, "check_command", side_effect=RuntimeError("boom")):
            resp = call({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                         "params": {"name": "customs.check", "arguments": {"command": "pip install x"}}})
        self.assertEqual(resp["result"]["structuredContent"]["overall"], "inspect")

    def test_no_install_is_clear(self):
        with mock.patch.object(mcp_server, "check_command", return_value=[]):
            resp = call({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                         "params": {"name": "customs.check", "arguments": {"command": "ls"}}})
        self.assertEqual(resp["result"]["structuredContent"]["overall"], "clear")


class StdioTests(unittest.TestCase):
    def test_serve_reads_lines_and_writes_replies(self):
        requests = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            "not json",
        ]) + "\n"
        out = io.StringIO()
        self.assertEqual(mcp_server.serve(io.StringIO(requests), out), 0)
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(replies[0]["id"], 1)
        self.assertEqual(replies[1]["error"]["code"], -32700)
        self.assertEqual(len(replies), 2)


if __name__ == "__main__":
    unittest.main()
