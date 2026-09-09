import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

BINARY = str(pathlib.Path(sys.argv.pop(1)).resolve())


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='migrator-regression-')
        self.addCleanup(self.temp.cleanup)
        self.repo = pathlib.Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args])

    def put(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def migrate(self, mode='platform_first'):
        return subprocess.run([BINARY, '--repo', str(self.repo), '--mode', mode, '-y'],
                              capture_output=True, timeout=30)

    def test_dirty_worktree_is_preserved(self):
        self.put('README.md', 'committed')
        self.commit()
        head = self.git('rev-parse', 'HEAD')
        for kind in ('unstaged', 'staged', 'untracked'):
            with self.subTest(kind=kind):
                self.git('restore', '--staged', '--worktree', '.')
                path = 'new.txt' if kind == 'untracked' else 'README.md'
                self.put(path, 'valuable work')
                if kind == 'staged':
                    self.git('add', path)
                before = self.git('status', '--porcelain')
                self.assertNotEqual(self.migrate().returncode, 0)
                self.assertEqual(self.git('rev-parse', 'HEAD'), head)
                self.assertEqual(self.git('status', '--porcelain'), before)
                self.assertEqual((self.repo / path).read_text(), 'valuable work')
                self.assertEqual(self.git('branch', '--list', 'backup-before-migration'), b'')

    def test_collisions_are_rejected_before_rewriting(self):
        self.put('Python/백준/Bronze/1/a.py', 'python')
        self.put('PyPy3/백준/Bronze/1/a.py', 'pypy')
        self.commit()
        for historical in (False, True):
            if historical:
                (self.repo / 'PyPy3/백준/Bronze/1/a.py').unlink()
                self.commit()
            for mode in ('platform_first', 'language_first', 'flat'):
                with self.subTest(historical=historical, mode=mode):
                    head = self.git('rev-parse', 'HEAD')
                    result = self.migrate(mode)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b'collision', result.stderr)
                    self.assertEqual(self.git('rev-parse', 'HEAD'), head)
                    self.assertEqual(self.git('status', '--porcelain'), b'')
                    self.assertEqual(self.git('branch', '--list', 'backup-before-migration'), b'')

    def test_remote_results_and_backups_are_retained(self):
        self.put('Python/백준/Bronze/1/a.py', 'solution')
        self.commit()
        original = self.git('rev-parse', 'HEAD')
        root = pathlib.Path(self.temp.name)
        remote = root / 'origin.git'
        subprocess.check_call(['git', 'clone', '--bare', str(self.repo), str(remote)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        config = root / 'gitconfig'
        config.write_text('[url "' + remote.as_uri() + '"]\n'
                          '    insteadOf = https://migrator.test/repo\n')
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM='1',
                   TMPDIR=str(root), TMP=str(root), TEMP=str(root))
        for action in ('cancel', 'yes_flag', 'failed_push', 'successful_push'):
            with self.subTest(action=action):
                subprocess.check_call(['git', '-C', str(remote), 'config',
                                       'receive.denyNonFastForwards',
                                       'true' if action == 'failed_push' else 'false'])
                args = [BINARY, '--repo', 'https://migrator.test/repo',
                        '--mode', 'platform_first']
                if action == 'yes_flag':
                    args.append('-y')
                result = subprocess.run(args, input='y\nn\n' if action == 'cancel' else 'y\ny\n',
                                        text=True, capture_output=True, env=env, timeout=30)
                self.assertEqual(result.returncode, 1 if action == 'failed_push' else 0,
                                 result.stdout + result.stderr)
                retained = result.stdout.split('[+] Repository retained at: ', 1)[1].splitlines()[0]
                target = pathlib.Path(retained)
                self.assertTrue((target / '백준/Bronze/1/a.py').is_file())
                backup = subprocess.check_output(['git', '-C', retained, 'rev-parse',
                                                  'backup-before-migration'])
                self.assertEqual(backup, original)
                if action == 'failed_push':
                    self.assertNotIn('Push completed successfully', result.stdout)
                remote_head = subprocess.check_output(['git', '-C', str(remote), 'rev-parse', 'main'])
                if action == 'successful_push':
                    self.assertNotEqual(remote_head, original)
                else:
                    self.assertEqual(remote_head, original)


if __name__ == '__main__':
    unittest.main()
