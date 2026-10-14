import unittest,tempfile,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
import numpy as np
import soundfile as sf
from capture import Capture,recover_partial
from core import atomic_json,read_json

class FakeStream:
    def __init__(self,fail=False):self.n=0;self.fail=fail
    def start_stream(self):pass
    def stop_stream(self):pass
    def close(self):pass
    def get_read_available(self):return 1600
    def read(self,frames,exception_on_overflow=True):
        time.sleep(.001);self.n+=1
        if self.fail and self.n==5:raise OSError('test device unplugged')
        if self.n>160:time.sleep(.01)
        return np.zeros((frames,2),dtype=np.int16).tobytes()

class FakeAudio:
    def __init__(self,fail=False):self.fail=fail
    def get_host_api_info_by_type(self,x):return dict(defaultInputDevice=1)
    def get_device_info_by_index(self,x):return dict(index=1,defaultSampleRate=16000,maxInputChannels=2)
    def open(self,**kw):return FakeStream(self.fail)
    def terminate(self):pass

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'audio').mkdir()
    def tearDown(self):self.tmp.cleanup()
    def test_stop_flushes_short_tail_and_manifest(self):
        with patch('capture.pa.PyAudio',return_value=FakeAudio()):
            c=Capture(self.root,{});c.start();time.sleep(.03);c.stop()
        files=list((self.root/'audio').glob('*.wav'));self.assertTrue(files)
        self.assertTrue((self.root/'capture_done.json').exists())
        for p in files:
            self.assertGreater(sf.info(p).duration,0)
            self.assertEqual(read_json(p.with_suffix('.json'))['file'],p.name)
        self.assertFalse(list((self.root/'audio').glob('*.part.wav')))
    def test_device_failure_keeps_partial_audio(self):
        with patch('capture.pa.PyAudio',return_value=FakeAudio(fail=True)):
            c=Capture(self.root,{});c.start();self.assertTrue(c.stop_event.wait(3));c.stop()
        self.assertTrue(c.errors);self.assertTrue(list((self.root/'audio').glob('*.wav')))
        self.assertTrue(read_json(self.root/'capture_done.json')['errors'])
    def test_recover_unexpected_shutdown(self):
        path=self.root/'audio/mic_0000000.part.wav'
        sf.write(path,np.zeros(16000,dtype=np.float32),16000)
        atomic_json(path.with_suffix('.json'),dict(source='mic',offset=12,rate=16000))
        recover_partial(self.root)
        self.assertTrue((self.root/'audio/mic_0000000.wav').exists())
        meta=read_json(self.root/'audio/mic_0000000.json')
        self.assertEqual(meta['duration'],1.);self.assertEqual(meta['offset'],12)
    def test_idle_loopback_stop_never_blocks(self):
        class IdleStream(FakeStream):
            def get_read_available(self):return 0
            def read(self,*args,**kwargs):raise AssertionError('idle stream must not be read')
        class IdleAudio(FakeAudio):
            def open(self,**kwargs):return IdleStream()
        with patch('capture.pa.PyAudio',return_value=IdleAudio()):
            c=Capture(self.root,{});c.start();time.sleep(.02)
            start=time.monotonic();c.stop()
        self.assertLess(time.monotonic()-start,1.)
        self.assertFalse(c.errors)
    def test_stop_drains_the_buffered_tail(self):
        class TailStream(FakeStream):
            def get_read_available(self):return 3200
        c=Capture(self.root,{});c.started=time.monotonic();c.stop_event.set()
        c._record('mic',TailStream(),16000,2)
        p=next((self.root/'audio').glob('*.wav'))
        self.assertEqual(sf.info(p).frames,3200)

if __name__=='__main__':unittest.main()
