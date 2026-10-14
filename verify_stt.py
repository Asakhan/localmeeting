from pathlib import Path
import urllib.request, json, time, sys, os
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
from core import settings,atomic_json
from engine import SpeechEngine
out=root/'test-output';out.mkdir(exist_ok=True)
for name,url in [('ko.wav','https://huggingface.co/k2-fsa/sherpa-onnx-zipformer-korean-2024-06-24/resolve/main/test_wavs/0.wav'),('en.wav','https://raw.githubusercontent.com/openai/whisper/main/tests/jfk.flac')]:
    p=out/name
    if not p.exists():urllib.request.urlretrieve(url,p)
c=settings();c['model_root']=str(root/'models')
e=SpeechEngine(c,out)
import soundfile as sf, psutil
info=sf.info(str(out/'ko.wav'))
t=time.perf_counter();rows=e.process(out/'ko.wav',dict(source='mic',offset=0))
report=dict(duration=info.duration,processing_seconds=time.perf_counter()-t,rows=rows,rss_gib=psutil.Process().memory_info().rss/2**30)
atomic_json(out/'stt_ko.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
