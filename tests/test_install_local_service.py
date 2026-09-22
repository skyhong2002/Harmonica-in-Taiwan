import io
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import install_local_service as installer


class LocalInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'checkout'
        (self.root / '.venv/bin').mkdir(parents=True)
        (self.root / '.venv/bin/python').write_text('test executable placeholder')
        self.root_patch = patch.object(installer, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_dry_run_generates_loopback_config_without_loading_service(self):
        with patch.object(sys, 'argv', ['install_local_service.py', '--public-origin', 'https://atlas.example']), patch('install_local_service.subprocess.run') as run, patch('sys.stdout', io.StringIO()):
            self.assertEqual(installer.main(), 0)
        run.assert_not_called()
        path = self.root / 'state/tw.observe.harmonica.web.plist'
        value = plistlib.loads(path.read_bytes())
        self.assertEqual(value['WorkingDirectory'], str(self.root))
        self.assertEqual(value['ProgramArguments'], [str(self.root / '.venv/bin/python'), str(self.root / 'scripts/serve.py'), '--host', '127.0.0.1', '--port', '8330'])
        self.assertEqual(value['EnvironmentVariables']['HARMONICA_PUBLIC_ORIGIN'], 'https://atlas.example')
        self.assertEqual(value['EnvironmentVariables']['HARMONICA_TRUST_PROXY'], '1')
        self.assertTrue(value['KeepAlive'])
        self.assertNotIn('APIFY_TOKEN', value['EnvironmentVariables'])
        self.assertFalse((Path(self.temp.name) / 'Library/LaunchAgents').exists())

    def test_install_uses_current_user_domain_and_only_web_label(self):
        home = Path(self.temp.name) / 'home'
        with patch.object(sys, 'argv', ['install_local_service.py', '--install']), patch.object(sys, 'platform', 'darwin'), patch.object(Path, 'home', return_value=home), patch('install_local_service.subprocess.run') as run, patch('install_local_service.os.getuid', return_value=1234), patch('sys.stdout', io.StringIO()):
            self.assertEqual(installer.main(), 0)
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls[0], ['launchctl', 'bootout', 'gui/1234/tw.observe.harmonica.web'])
        self.assertEqual(calls[1], ['launchctl', 'bootstrap', 'gui/1234', str(home / 'Library/LaunchAgents/tw.observe.harmonica.web.plist')])
        self.assertTrue((home / 'Library/LaunchAgents/tw.observe.harmonica.web.plist').exists())

    def test_insecure_or_path_origin_rejected_without_generated_config(self):
        for origin in ('http://atlas.example', 'https://atlas.example/path', 'https://user@atlas.example'):
            with patch.object(sys, 'argv', ['install_local_service.py', '--public-origin', origin]), patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
                installer.main()
        self.assertFalse((self.root / 'state').exists())


if __name__ == '__main__':
    unittest.main()
