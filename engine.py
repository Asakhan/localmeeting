"""Offline transcription worker. Only bounded 12-second chunks enter RAM."""
from pathlib import Path
import os, sys, time, subprocess, gc, json, traceback
from core import atomic_json, read_json, append_jsonl, ROOT, recognition_glossary
from speech_quality import word_rejection, speaker_for_word

ASR_REVISION='large-v3-int8-evidence-v2'

_DLL_HANDLES=[]
def credible_segment(segment):
    # Whisper can append a whole invented sentence at a zero-length audio tail.
    # Keep short actual syllables, reject multi-character near-zero-duration text.
    import re
    chars=len(re.sub(r'\W','',segment.text,flags=re.UNICODE))
    return not (segment.end-segment.start<0.08 and chars>=3)

def runtime_setup(threads=4):
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
        os.environ[key]=str(threads)
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        candidates=[ROOT/'cuda',Path(getattr(sys,'_MEIPASS',ROOT))/'cuda']
        for base in [Path(sys.prefix)/'Lib/site-packages',Path(getattr(sys,'_MEIPASS',ROOT))]:
            candidates += [base/'nvidia/cublas/bin',base/'nvidia/cudnn/bin',base/'nvidia/cuda_nvrtc/bin']
        for p in candidates:
            if p.is_dir():
                _DLL_HANDLES.append(os.add_dll_directory(str(p)))
                os.environ['PATH']=str(p)+os.pathsep+os.environ.get('PATH','')

def gpu_free():
    try:
        p=subprocess.run(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return int(p.stdout.splitlines()[0])
    except Exception:return 0

def event(folder,kind,message,**kw):
    atomic_json(Path(folder)/'worker_status.json',dict(kind=kind,message=message,updated=time.time(),**kw))

class SpeechEngine:
    def __init__(self,config,folder):
        runtime_setup(config['threads'])
        import numpy as np
        import sherpa_onnx as so
        from faster_whisper import WhisperModel
        self.np=np;self.folder=Path(folder);self.config=config
        modelroot=Path(config['model_root'])
        # The fine-tuned medium model repeatedly appended invented dialogue.
        # Both language modes now use the verified large-v3 weights, one resident model.
        choice='large-v3'
        self.device='cuda' if config['device']!='cpu' and gpu_free()>4200 else 'cpu'
        event(folder,'loading',f'음성 모델 준비 중 · {self.device.upper()}'+(' · 실시간 표시가 지연될 수 있습니다.' if self.device=='cpu' else ''))
        self.whisper=WhisperModel(str(modelroot/choice),device=self.device,
            compute_type='int8_float16' if self.device=='cuda' else 'int8',cpu_threads=config['threads'],num_workers=1,local_files_only=True)
        emb=so.SpeakerEmbeddingExtractorConfig(model=str(modelroot/'speaker-eres2net.onnx'),num_threads=2,provider='cpu')
        self.extractor=so.SpeakerEmbeddingExtractor(emb)
        seg=so.OfflineSpeakerSegmentationModelConfig(pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(modelroot/'segmentation-fp32.onnx')),num_threads=2,provider='cpu')
        cfg=so.OfflineSpeakerDiarizationConfig(segmentation=seg,embedding=emb,
             clustering=so.FastClusteringConfig(num_clusters=-1,threshold=0.5),min_duration_on=0.3,min_duration_off=0.25)
        self.diarizer=so.OfflineSpeakerDiarization(cfg)
        self.centroids=[]
        self.last_quality={}

    def embedding(self,samples):
        if len(samples)<8000:return None
        stream=self.extractor.create_stream();stream.accept_waveform(16000,samples);stream.input_finished()
        if not self.extractor.is_ready(stream):return None
        vec=self.np.asarray(self.extractor.compute(stream),dtype=self.np.float32)
        return vec/(self.np.linalg.norm(vec)+1e-8)

    def speaker(self,vec,source,excluded=()):
        if vec is None:return '화자 미확인'
        np=self.np
        scores=[float(np.dot(vec,x['vec'])) if x['source']==source and f'참석자{i+1}' not in excluded else -1. for i,x in enumerate(self.centroids)]
        threshold=max(.1,self.config.get('speaker_threshold',0.65)-.3)
        if scores and max(scores)>=threshold:
            i=int(np.argmax(scores));old=self.centroids[i]
            # Slow update prevents short/noisy turns from moving identity abruptly.
            v=np.asarray(old['vec'])*0.9+vec*0.1
            old['vec']=(v/(np.linalg.norm(v)+1e-8)).tolist()
            return f'참석자{i+1}'
        if len(self.centroids)>=64:return '화자 미확인'
        self.centroids.append(dict(source=source,vec=vec.tolist()))
        return f'참석자{len(self.centroids)}'

    def process(self,path,meta):
        import soundfile as sf
        from scipy.signal import resample_poly
        from math import gcd
        np=self.np
        audio,sr=sf.read(str(path),dtype='float32',always_2d=False)
        if audio.ndim>1:audio=audio.mean(axis=1)
        if sr!=16000:
            g=gcd(sr,16000);audio=resample_poly(audio,16000//g,sr//g).astype(np.float32)
        self.last_quality=dict(revision=ASR_REVISION,rejected=[],uncertain_words=0)
        if len(audio)<1600:return []
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        vad=get_speech_timestamps(audio,VadOptions(threshold=.55,min_speech_duration_ms=160,
             min_silence_duration_ms=350,speech_pad_ms=80))
        regions=[(x['start']/16000,x['end']/16000) for x in vad]
        self.last_quality['speech_regions']=regions
        if not regions:return []
        segments,info=self.whisper.transcribe(audio,language='ko' if self.config['language']=='ko' else None,
            multilingual=self.config['language']!='ko',task='transcribe',beam_size=5,temperature=0,
            condition_on_previous_text=False,word_timestamps=True,vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=350,speech_pad_ms=180),
            # Vocabulary hints are hints, not an initial sentence for the decoder to continue.
            initial_prompt=None,hotwords=recognition_glossary(self.config.get('glossary','')),
            hallucination_silence_threshold=.5,no_speech_threshold=.5,log_prob_threshold=-.8,
            compression_ratio_threshold=2.2,without_timestamps=False)
        segments=list(segments)
        if not segments:return []
        turns=self.diarizer.process(audio).sort_by_start_time()
        mapping={}
        for speaker_id in sorted({s.speaker for s in turns}):
            pieces=[audio[int(s.start*16000):int(s.end*16000)] for s in turns if s.speaker==speaker_id]
            # Embedding only speech spans, capped at 12s.
            voice=np.concatenate(pieces) if pieces else np.array([],dtype=np.float32)
            mapping[speaker_id]=self.speaker(self.embedding(voice),meta['source'],mapping.values())
        rows=[]
        for segment in segments:
            if not credible_segment(segment):
                self.last_quality['rejected'].append(dict(reason='implausible_segment',start=segment.start,end=segment.end))
                continue
            if segment.no_speech_prob>.6 and segment.avg_logprob < -.8:
                self.last_quality['rejected'].append(dict(reason='no_speech',start=segment.start,end=segment.end))
                continue
            words=segment.words or []
            if not words:
                # Do not publish guessed text without word alignment evidence.
                self.last_quality['rejected'].append(dict(reason='missing_alignment',start=segment.start,end=segment.end))
                continue
            for w in words:
                reason=word_rejection(w,regions,len(audio)/16000)
                if reason:
                    self.last_quality['rejected'].append(dict(reason=reason,start=float(w.start),end=float(w.end)))
                    if reason!='low_confidence':continue
                    # Do not publish a guessed proper name as a confident utterance.
                    self.last_quality['uncertain_words']+=1
                speaker=speaker_for_word(w,turns,mapping)
                text=' [청취 불명확]' if reason else w.word
                start=meta['offset']+w.start;end=meta['offset']+w.end
                if rows and rows[-1]['speaker']==speaker and start-rows[-1]['end']<1.2:
                    rows[-1]['text']+=text;rows[-1]['end']=end
                else:rows.append(dict(start=start,end=end,speaker=speaker,text=text,source=meta['source'],words=[]))
                rows[-1]['words'].append(dict(start=start,end=end,text=text))
        for row in rows:row['text']=row['text'].strip()
        return [r for r in rows if r['text']]

def rebuild_transcript(folder):
    results=[]
    for p in (folder/'results').glob('*.json'):
        r=read_json(p,{})
        results.extend(r.get('rows',[]))
    results.sort(key=lambda x:x['start'])
    temp=folder/'transcript.tmp'
    with temp.open('w',encoding='utf-8') as f:
        for row in results:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        f.flush();os.fsync(f.fileno())
    os.replace(temp,folder/'transcript.jsonl')
    return results

def run_transcription(folder):
    import psutil
    folder=Path(folder);meta=read_json(folder/'meeting.json');config=meta['config']
    (folder/'results').mkdir(exist_ok=True)
    runtime_setup(config['threads'])
    try:
        if psutil.virtual_memory().available<4*1024**3:
            raise RuntimeError('사용 가능한 RAM이 4GB 미만입니다. 다른 앱을 닫은 후 재처리하세요. 녹음은 보존됩니다.')
        engine=SpeechEngine(config,folder)
        checkpoints=[(p,read_json(p,{})) for p in (folder/'results').glob('*.json')]
        previous=None
        if checkpoints:
            previous,state=max(checkpoints,key=lambda item:item[1].get('order',0))
            # Old WeSpeaker checkpoints contain 256-D vectors; ERes2Net uses
            # 512-D vectors. Never compare embeddings from different models.
            engine.centroids=state.get('centroids',[]) if state.get('embedding_revision')=='eres2net-v1' else []
        del checkpoints
        rebuild_transcript(folder)
        while True:
            jobs=[]
            for p in (folder/'audio').glob('*.json'):
                j=read_json(p,{})
                if 'file' in j and not (folder/'results'/(p.stem+'.json')).exists():jobs.append((p,j))
            jobs.sort(key=lambda v:v[1]['offset'])
            if not jobs:
                if (folder/'capture_done.json').exists():break
                time.sleep(.3);continue
            for p,j in jobs:
                if psutil.virtual_memory().available<2*1024**3:
                    raise RuntimeError('RAM 여유가 부족하여 분석을 중지했습니다. 원음은 보존됩니다.')
                event(folder,'transcribing',f'발언 분석 중 · 대기 {len(jobs)}개',device=engine.device)
                started=time.perf_counter()
                rows=engine.process(folder/'audio'/j['file'],j)
                current=folder/'results'/(p.stem+'.json')
                atomic_json(current,dict(rows=rows,centroids=engine.centroids,embedding_revision='eres2net-v1',order=time.time(),seconds=time.perf_counter()-started,duration=j['duration'],quality=engine.last_quality))
                if previous and previous!=current:
                    old=read_json(previous,{})
                    if 'centroids' in old:
                        old.pop('centroids',None);atomic_json(previous,old)
                previous=current
                rebuild_transcript(folder)
                event(folder,'listening','실시간 기록 중',device=engine.device,speakers=len(engine.centroids))
        del engine
        gc.collect()
        from diarization import rediarize
        from core import transcript
        if transcript(folder):rediarize(folder,config)
        event(folder,'transcribed','전사 완료 · 음성 모델 해제 중')
        return 0
    except Exception as e:
        (folder/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        event(folder,'error',str(e));return 1
