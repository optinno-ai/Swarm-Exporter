import argparse
import unittest
from unittest.mock import MagicMock, patch

import swarm_exporter


class LocaleTests(unittest.TestCase):
    def test_normalize_locale(self):
        self.assertEqual(swarm_exporter.normalize_locale("ja_JP.UTF-8"), "ja")
        self.assertEqual(swarm_exporter.normalize_locale("pt-br"), "pt")

    def test_rejects_invalid_locale(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            swarm_exporter.normalize_locale("ja\r\nInjected: value")

    @patch("swarm_exporter.sys.platform", "darwin")
    @patch("swarm_exporter.subprocess.run")
    def test_macos_locale_takes_priority_over_process_locale(self, run):
        run.return_value = MagicMock(returncode=0, stdout="ja_JP\n")
        with patch("swarm_exporter.locale.getlocale", return_value=("C", "UTF-8")):
            self.assertEqual(swarm_exporter.detect_os_locale(), "ja")

    @patch("swarm_exporter.urllib.request.urlopen")
    def test_request_sends_accept_language(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        urlopen.return_value = response

        with patch("swarm_exporter.json.load", return_value={"meta": {"code": 200}}):
            swarm_exporter.request_page("token", "20231010", 1, 0, "ja")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Accept-language"), "ja")


if __name__ == "__main__":
    unittest.main()
