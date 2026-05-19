import ssl
import unittest
from unittest.mock import MagicMock, patch

import app.crawler as crawler


class CrawlerTlsTests(unittest.TestCase):
    def test_build_ssl_context_loads_bundled_twca_chain(self) -> None:
        fake_context = MagicMock()

        with patch.object(crawler.ssl, "create_default_context", return_value=fake_context) as create_default_context:
            context = crawler._build_ssl_context()

        self.assertIs(context, fake_context)
        create_default_context.assert_called_once_with()
        fake_context.load_verify_locations.assert_called_once_with(cafile=str(crawler.TWCA_CA_BUNDLE_PATH))

    def test_fetch_text_uses_client_ssl_context(self) -> None:
        response = MagicMock()
        response.read.return_value = b"demo"
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        ssl_context = ssl.create_default_context()

        with patch.object(crawler, "urlopen", return_value=response) as urlopen_mock:
            client = crawler.MoexClient(ssl_context=ssl_context)
            text = client._fetch_text("https://example.test")

        self.assertEqual(text, "demo")
        _, kwargs = urlopen_mock.call_args
        self.assertIs(kwargs["context"], ssl_context)


if __name__ == "__main__":
    unittest.main()
