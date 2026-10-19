import unittest

from customs.llm import DEFAULT_BASE_URL, Settings, TokenFactory, TokenFactoryError


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, body, headers):
        self.calls.append((url, body, headers))
        return self.response


class SettingsTests(unittest.TestCase):
    def test_missing_key_is_a_clear_error(self):
        with self.assertRaisesRegex(TokenFactoryError, "NEBIUS_API_KEY"):
            Settings.from_env({})

    def test_defaults_and_trailing_slash(self):
        s = Settings.from_env({"NEBIUS_API_KEY": "k"})
        self.assertEqual(s.base_url, DEFAULT_BASE_URL)
        s = Settings.from_env({"NEBIUS_API_KEY": "k", "CUSTOMS_TF_BASE_URL": "https://example.test/v1"})
        self.assertEqual(s.base_url, "https://example.test/v1/")

    def test_model_ids_come_from_env_only(self):
        s = Settings.from_env({"NEBIUS_API_KEY": "k", "CUSTOMS_MODEL_NANO": "vendor/nano-x"})
        self.assertEqual(s.nano, "vendor/nano-x")
        self.assertIsNone(s.super)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(api_key="secret", base_url=DEFAULT_BASE_URL, nano="m-nano")

    def test_chat_sends_bearer_and_returns_content(self):
        t = FakeTransport({"choices": [{"message": {"content": "ready"}}]})
        reply = TokenFactory(self.settings, t).chat("m-nano", [{"role": "user", "content": "hi"}])
        self.assertEqual(reply, "ready")
        url, body, headers = t.calls[0]
        self.assertEqual(url, DEFAULT_BASE_URL + "chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer secret")
        self.assertEqual(body["model"], "m-nano")

    def test_unexpected_response_shape_raises(self):
        t = FakeTransport({"error": "nope"})
        with self.assertRaises(TokenFactoryError):
            TokenFactory(self.settings, t).chat("m", [])

    def test_list_models(self):
        t = FakeTransport({"data": [{"id": "a"}, {"id": "nvidia/nemotron-x"}]})
        self.assertEqual(TokenFactory(self.settings, t).list_models(), ["a", "nvidia/nemotron-x"])
        self.assertEqual(t.calls[0][0], DEFAULT_BASE_URL + "models")

    def test_require_model_when_unset(self):
        client = TokenFactory(Settings(api_key="k"), FakeTransport({}))
        with self.assertRaisesRegex(TokenFactoryError, "CUSTOMS_MODEL_NANO"):
            client.require_model("nano")


if __name__ == "__main__":
    unittest.main()
