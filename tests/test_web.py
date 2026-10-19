import unittest
from unittest import mock

from customs import web
from customs.parser import Declaration, Ecosystem
from customs.verdict import Decision, Verdict


class RenderTests(unittest.TestCase):
    def test_stats_without_results(self):
        with mock.patch.object(web, "_load_results", return_value=None):
            self.assertIn("No evaluation run yet", web.page())

    def test_stats_show_rates(self):
        summary = {"run_at": "t", "cases": 22, "catch_rate": 1.0, "caught": 12, "attacks": 12,
                   "false_block_rate": 0.0, "false_blocks": 0, "clean": 10,
                   "latency_ms_median": 500.0, "latency_ms_p95": 2000.0}
        with mock.patch.object(web, "_load_results", return_value=summary):
            html_out = web.page()
        self.assertIn("100%", html_out)
        self.assertIn("12 of 12 fabricated names", html_out)

    def test_command_is_escaped_in_form(self):
        with mock.patch.object(web, "_load_results", return_value=None):
            html_out = web.page(command='pip install "x"<script>alert(1)</script>')
        self.assertNotIn("<script>alert(1)", html_out)
        self.assertIn("&lt;script&gt;", html_out)

    def test_verdict_output_escapes_names_and_shows_suggestion(self):
        decision = Decision(Declaration(Ecosystem.PYPI, "<b>x</b>"), Verdict.BLOCK,
                            ["does not exist"], suggestion="requests")
        with mock.patch.object(web, "check_command", return_value=[decision]):
            out = web.render_verdict("pip install <b>x</b>")
        self.assertNotIn("<b>x</b>", out)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", out)
        self.assertIn("Did you mean", out)
        self.assertIn("v-BLOCK", out)

    def test_no_install_message(self):
        with mock.patch.object(web, "check_command", return_value=[]):
            self.assertIn("No install", web.render_verdict("ls"))


if __name__ == "__main__":
    unittest.main()
