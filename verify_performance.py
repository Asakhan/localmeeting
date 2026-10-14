from pathlib import Path
import time,json,sys
from core import ROOT,settings,atomic_json
from engine import SpeechEngine
import soundfile as sf,numpy as np
c=settings();c['model_root']=str(ROOT/'models');out=ROOT/'test-output'
a,sr=sf.read(out/'ko.wav',dtype='float32');clip=np.concatenate([a,np.zeros(sr,dtype='float32'),a,np.zeros(sr,dtype='float32'),a]);sf.write(out/'ko-long.wav',clip,sr)
e=SpeechEngine(c,out);reports=[]
for name in ['ko.wav','ko-long.wav','ko.wav']:
    t=time.perf_counter();rows=e.process(out/name,dict(source='mic',offset=0));result=dict(file=name,duration=sf.info(out/name).duration,seconds=time.perf_counter()-t,rows=rows);reports.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
atomic_json(out/'stt_repeat.json',reports)
