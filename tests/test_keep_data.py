"""launch.sh's keep_data: the board shell code that moves persisted packages' app data out of old stages."""

import os
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

LAUNCH = Path(__file__).resolve().parent.parent / 'device' / 'launch.sh'


def keep_data_command(files: Path, persist: str, keep_pattern: str) -> str:
    """keep_data's output for a host files directory at `files` (the board's is /data/app/el2/...)."""
    function = re.search(r'^keep_data\(\) \{\n.*?^\}\n', LAUNCH.read_text(), re.S | re.M)[0]
    script = (f'PERSIST_DATA="{persist}"; HOST_FILES={files}; KEEP_DATA_DIR=$HOST_FILES/a2hlab-data\n'
              f'{function}keep_data {shlex.quote(keep_pattern)}\n')
    return subprocess.run(['bash', '-c', script], capture_output=True, text=True, check=True).stdout


class KeepDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.files = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def stage(self, name: str, age: int, **packages: str) -> None:
        """A stage whose app-data holds one marker file per package, `age` seconds old."""
        stage = self.files / ('a2hlab-source-' + name)
        for package, marker in packages.items():
            data = stage / 'app-data' / package.replace('_', '.')
            data.mkdir(parents=True)
            (data / 'marker').write_text(marker)
        os.utime(stage, (1_700_000_000 - age, 1_700_000_000 - age))

    def kept(self, package: str) -> str:
        marker = self.files / 'a2hlab-data' / package / 'marker'
        return marker.read_text() if marker.exists() else ''

    def run_board(self, command: str) -> None:
        subprocess.run(['sh', '-c', command], check=True)

    def test_newest_stage_wins_and_the_kept_stage_stays(self) -> None:
        self.stage('old', 300, com_google_android_gms='old')
        self.stage('new', 100, com_google_android_gms='new', com_example_app='app')
        self.stage('running', 10, com_google_android_gms='running')
        self.run_board(keep_data_command(self.files, 'com.google.android.gms com.android.vending', '*running*'))
        self.assertEqual(self.kept('com.google.android.gms'), 'new')
        # The running stage keeps its data in place; packages not named are left for the stage's deletion.
        self.assertTrue((self.files / 'a2hlab-source-running/app-data/com.google.android.gms/marker').exists())
        self.assertFalse((self.files / 'a2hlab-data/com.example.app').exists())
        self.assertTrue((self.files / 'a2hlab-source-new/app-data/com.example.app/marker').exists())

    def test_both_hosts_stages_stay(self) -> None:
        """KEEP_STAGE with the Play services host's and the Play Store host's stages: neither moves."""
        self.stage('old', 300, com_google_android_gms='old', com_android_vending='old')
        self.stage('play', 20, com_google_android_gms='play')
        self.stage('store', 10, com_android_vending='store')
        self.run_board(keep_data_command(self.files, 'com.google.android.gms com.android.vending', '*play*|*store*'))
        self.assertEqual(self.kept('com.google.android.gms'), 'old')
        self.assertEqual(self.kept('com.android.vending'), 'old')
        self.assertTrue((self.files / 'a2hlab-source-play/app-data/com.google.android.gms/marker').exists())
        self.assertTrue((self.files / 'a2hlab-source-store/app-data/com.android.vending/marker').exists())

    def test_keep_pattern_from_stage_list(self) -> None:
        """launch.sh turns KEEP_STAGE's space-separated hashes into one case pattern."""
        block = re.search(r'^KEEP_PATTERN=.*\n.*\n', LAUNCH.read_text(), re.M)[0]
        for stages, expected in (('aa bb', '*aa*|*bb*'), ('aa', '*aa*'), ('', '@none@')):
            out = subprocess.run(['bash', '-c', 'KEEP_STAGE="%s"\n%secho "$KEEP_PATTERN"' % (stages, block)],
                                 capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(out, expected)

    def test_kept_data_survives_a_stage_without_it(self) -> None:
        (self.files / 'a2hlab-data/com.google.android.gms').mkdir(parents=True)
        (self.files / 'a2hlab-data/com.google.android.gms/marker').write_text('earlier')
        self.stage('client', 50, com_example_app='app')
        self.run_board(keep_data_command(self.files, 'com.google.android.gms', '@none@'))
        self.assertEqual(self.kept('com.google.android.gms'), 'earlier')

    def test_empty_list_keeps_nothing(self) -> None:
        self.assertEqual(keep_data_command(self.files, '', '@none@'), '')


if __name__ == '__main__':
    unittest.main()
