from core import ROOT,settings,atomic_json
from engine import SpeechEngine
from pathlib import Path
import json,time,numpy as np,soundfile as sf
from scipy.signal import resample_poly
c=settings();c['model_root']=str(ROOT/'models');c['language']='mixed'
out=ROOT/'test-output';e=SpeechEngine(c,out)
reports=[]
for file in ['ko.wav','en.wav']:
    t=time.perf_counter();rows=e.process(out/file,dict(source='mic',offset=0));report=dict(file=file,duration=sf.info(out/file).duration,seconds=time.perf_counter()-t,rows=rows);reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
atomic_json(out/'stt_mixed.json',reports)
