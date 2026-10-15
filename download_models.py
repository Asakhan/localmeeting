from pathlib import Path
import json, urllib.request, shutil, tarfile, time
ROOT=Path(__file__).resolve().parent
MODELS=ROOT/'models'
MODELS.mkdir(exist_ok=True)
def download(url, path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): print('EXISTS',path.name,flush=True); return
    tmp=path.with_suffix(path.suffix+'.part')
    print('DOWNLOAD',path.name,flush=True)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url,timeout=90) as r, open(tmp,'wb') as f:
                shutil.copyfileobj(r,f,1024*1024*4)
            tmp.replace(path); print('DONE',path.name,path.stat().st_size,flush=True);return
        except Exception as e:
            print('RETRY',str(e),flush=True);time.sleep(2)
    raise RuntimeError(url)
def hf(repo, dest, names=None):
    d=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo))
    for x in d['siblings']:
        n=x['rfilename']
        if (names and n in names) or (not names and (n.endswith('.json') or n in ['model.bin','vocabulary.txt'])):
            download('https://huggingface.co/'+repo+'/resolve/main/'+n,MODELS/dest/n)
hf('seastar105/whisper-medium-komixv2','komix-source',['model.safetensors','config.json','generation_config.json','tokenizer_config.json','preprocessor_config.json','special_tokens_map.json','vocab.json','merges.txt','normalizer.json','added_tokens.json'])
hf('Systran/faster-whisper-large-v3','large-v3')
hf('unsloth/Qwen3.5-9B-GGUF','llm',['Qwen3.5-9B-Q4_K_M.gguf'])
base='https://github.com/k2-fsa/sherpa-onnx/releases/download/'
download(base+'speaker-recongition-models/wespeaker_en_voxceleb_resnet34.onnx',MODELS/'speaker.onnx')
download(base+'speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx',MODELS/'speaker-eres2net.onnx')
download(base+'speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2',MODELS/'segmentation.tar.bz2')
with tarfile.open(MODELS/'segmentation.tar.bz2') as t:
    m=next(m for m in t.getmembers() if m.name.endswith('/model.onnx'))
    with t.extractfile(m) as f,open(MODELS/'segmentation-fp32.onnx','wb') as o: shutil.copyfileobj(f,o)
print('ALL MODELS READY',flush=True)
