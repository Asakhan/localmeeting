"""Exercise actual Qt controls and worker lifecycle using a public audio fixture."""
from pathlib import Path
import time,shutil,sys
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from PySide6.QtCore import QTimer
from core import ROOT,atomic_json,read_json,now
import capture

class FixtureCapture:
    def __init__(self,folder,config):self.folder=folder;self.errors=[];self.levels={'mic':.2};self.started=0
    def start(self):
        self.started=time.monotonic()
        shutil.copy2(ROOT/'test-output/ko.wav',self.folder/'audio/mic_0000000.wav')
        atomic_json(self.folder/'audio/mic_0000000.json',dict(file='mic_0000000.wav',source='mic',offset=0,duration=3.5265))
    def stop(self):atomic_json(self.folder/'capture_done.json',dict(ended=now(),errors=[]))

if __name__=='__main__':
    capture.Capture=FixtureCapture
    from gui import Window,STYLE
    app=QApplication(sys.argv);app.setStyleSheet(STYLE);window=Window()
    window.config['folder']=str(ROOT/'test-output/gui-flow');window.config['model_root']=str(ROOT/'models')
    failures=[];window.error=lambda text:failures.append(text)
    window.show();window.start_button.click()
    QTimer.singleShot(500,window.stop_button.click)
    start=time.monotonic();done=False
    def check():
        global done
        if done:return
        if time.monotonic()-start>120:
            failures.append('GUI workflow timeout');done=True;app.quit();return
        if window.active is not None:return
        done=True
        try:
            assert not failures,failures
            assert window.selected is not None
            meta=read_json(window.selected/'meeting.json')
            assert meta.get('audio_deleted'),meta
            assert window.names.rowCount()>=1
            window.names.setItem(0,1,QTableWidgetItem('테스트 참석자'))
            window.rename_button.click()
            assert '테스트 참석자' in (window.selected/'전체전사.txt').read_text(encoding='utf-8-sig')
            window.grab().save(str(ROOT/'test-output/gui-library.png'))
            window.navigate(2);window.grab().save(str(ROOT/'test-output/gui-settings.png'))
            print('GUI record-stop-summary-rename PASS',flush=True)
        except Exception as e:failures.append(repr(e));print('FAIL',repr(e),flush=True)
        app.quit()
    timer=QTimer();timer.timeout.connect(check);timer.start(500)
    app.exec()
    for job in window.jobs:job.close()
    raise SystemExit(1 if failures else 0)
