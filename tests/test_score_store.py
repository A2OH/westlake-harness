"""device/play/score_store.py: Play client-library calls and callbacks per service family, from app hilogs."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / 'device' / 'play' / 'score_store.py'


def load():
    spec = importlib.util.spec_from_file_location('score_store', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line(pid, service, message, tag='PlayCore'):
    return (f'11-12 06:55:04.343 {pid} {pid + 1} I C00f00/{tag}: UID: [20010054]  PID: [{pid}] '
            f'{service} : {message}')


class ScoreStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self.tmp.name)
        self.score = load()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def app(self, package, *lines):
        (self.logs / f'hk-{package}.hilog').write_text('\n'.join(lines) + '\n')

    def test_callbacks_count_with_their_service(self):
        self.app('a.update', line(10, 'AppUpdateService', 'requestUpdateInfo(a.update)'),
                 line(10, 'OnRequestInstallCallback', 'onRequestInfo'))
        self.app('b.integrity', line(20, 'IntegrityService', 'requestIntegrityToken(IntegrityTokenRequest{nonce=x})'),
                 line(20, 'OnRequestIntegrityTokenCallback', 'onRequestIntegrityToken'),
                 line(20, 'IntegrityService', 'ServiceConnectionImpl.onServiceConnected(ComponentInfo{x/y})'))
        calls, callbacks, errors, _ = self.score.score(self.logs)
        self.assertEqual(calls['in-app update'], {'a.update'})
        self.assertEqual(dict(callbacks['in-app update']), {'onRequestInfo': {'a.update'}})
        # A service connection is not an answer.
        self.assertEqual(dict(callbacks['integrity']), {'onRequestIntegrityToken': {'b.integrity'}})
        self.assertEqual(dict(errors), {})

    def test_errors_and_families(self):
        self.app('c.assets', line(30, 'AssetPackServiceImpl', 'getPackStates([x])'),
                 line(30, 'AssetPackServiceImpl', 'onError(-2)'))
        self.app('d.split', line(40, 'SplitInstallService', 'startInstall([m],[])'),
                 line(40, 'SplitInstallService', 'onStartInstall(1)'),
                 'unrelated line without the tag')
        self.app('e.express', line(50, 'ExpressIntegrityService', 'warmUpIntegrityToken failed: -12'))
        calls, callbacks, errors, _ = self.score.score(self.logs)
        self.assertEqual(dict(errors['asset delivery']), {'-2': {'c.assets'}})
        self.assertEqual(dict(callbacks['split install']), {'onStartInstall': {'d.split'}})
        self.assertEqual(dict(errors['express integrity']), {'-12': {'e.express'}})
        self.assertNotIn('integrity', calls)

    def test_review_callback_counts_for_review(self):
        # Play Core's review callback logs under the in-app update callback's class name.
        self.app('h.review', line(80, 'ReviewService', 'requestInAppReview (h.review)'),
                 line(80, 'OnRequestInstallCallback', 'onGetLaunchReviewFlowInfo'))
        calls, callbacks, _, _ = self.score.score(self.logs)
        self.assertEqual(dict(callbacks['in-app review']), {'onGetLaunchReviewFlowInfo': {'h.review'}})
        self.assertNotIn('in-app update', calls)

    def test_binds_that_never_connect(self):
        self.app('i.age', line(90, 'AgeSignalsService', 'Initiate binding to the service.'))
        self.app('j.update', line(91, 'AppUpdateService', 'requestUpdateInfo(j.update)'),
                 line(91, 'AppUpdateService', 'Initiate binding to the service.'),
                 line(91, 'AppUpdateService', 'linkToDeath'))
        _, _, _, unconnected = self.score.score(self.logs)
        self.assertEqual(unconnected, {'AgeSignalsService': {'i.age'}})

    def test_list_limits_the_apps(self):
        self.app('f.one', line(60, 'ReviewService', 'requestInAppReview (f.one)'))
        self.app('g.two', line(70, 'ReviewService', 'requestInAppReview (g.two)'))
        calls, _, _, _ = self.score.score(self.logs, only={'g.two'})
        self.assertEqual(calls['in-app review'], {'g.two'})


if __name__ == '__main__':
    unittest.main()
