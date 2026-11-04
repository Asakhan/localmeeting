"""Regression: 2026-11-04 the worker died with WinError 5 because the GUI was
reading worker_status.json at the instant the worker replaced it."""
import unittest, tempfile, threading, time, sys, os
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import atomic_json, read_json, replace_file
import engine

class FileLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    @unittest.skipUnless(os.name=='nt','Windows sharing semantics')
    def test_replace_waits_for_reader_to_close(self):
        target=self.root/'worker_status.json'
        atomic_json(target,dict(kind='old'))
        handle=target.open('r',encoding='utf-8')  # same open mode as the GUI poller
        threading.Timer(0.4,handle.close).start()
        atomic_json(target,dict(kind='new'))
        self.assertEqual(read_json(target)['kind'],'new')
        self.assertEqual(list(self.root.glob('*.tmp')),[])

    def test_replace_gives_up_after_timeout_and_cleans_temp(self):
        with mock.patch('core.os.replace',side_effect=PermissionError(5,'denied')):
            with self.assertRaises(PermissionError):atomic_json(self.root/'a.json',{},timeout=0.1)
        self.assertEqual(list(self.root.glob('*.tmp')),[])

    def test_status_event_never_raises(self):
        with mock.patch('core.os.replace',side_effect=PermissionError(5,'denied')):
            with mock.patch('engine.atomic_json',wraps=lambda p,d,timeout=3.0:atomic_json(p,d,timeout=0.05)):
                engine.event(self.root,'listening','실시간 기록 중')

if __name__=='__main__':unittest.main()
