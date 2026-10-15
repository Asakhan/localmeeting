"""Build a Python-independent Windows folder distribution with local models."""
from pathlib import Path
import subprocess, sys, shutil, json

ROOT=Path(__file__).resolve().parent

def main():
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed',
          '--name','LocalMeeting','--onedir','--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build'),
          '--specpath',str(ROOT/'build'),'--paths',str(ROOT),
          '--version-file',str(ROOT/'version_info.txt'),
          '--collect-all','sherpa_onnx','--collect-all','sherpa_onnx_core',
          '--collect-all','faster_whisper','--collect-all','ctranslate2',
          '--collect-all','pyaudiowpatch','--collect-all','onnxruntime',
          '--collect-all','tokenizers','--collect-data','docx',
          '--collect-all','kiwipiepy','--collect-all','kiwipiepy_model',
          '--exclude-module','torch','--exclude-module','transformers',
          '--exclude-module','PySide6.QtWebEngineWidgets','--exclude-module','PySide6.QtWebEngineCore',
          '--exclude-module','PySide6.QtWebEngineQuick']
    dllroot=Path(sys.prefix)/'Lib/site-packages/nvidia'
    for directory in ['cublas/bin','cudnn/bin','cuda_nvrtc/bin']:
        for dll in (dllroot/directory).glob('*.dll'):args+=['--add-binary',f'{dll};cuda']
    args.append(str(ROOT/'app.py'))
    subprocess.run(args,cwd=ROOT,check=True)
    dest=ROOT/'dist/LocalMeeting'
    llama=Path('C:/AI/llama')
    target=dest/'runtime/llama';target.mkdir(parents=True,exist_ok=True)
    for p in llama.iterdir():
        if p.suffix=='.dll' or p.name in ['llama-server.exe','LICENSE-LLVM-OpenMP']:
            shutil.copy2(p,target/p.name)
    for name in ['large-v3','llm','kogrammar']:
        shutil.copytree(ROOT/'models'/name,dest/'models'/name,dirs_exist_ok=True)
    for name in ['speaker-eres2net.onnx','segmentation-fp32.onnx']:shutil.copy2(ROOT/'models'/name,dest/'models'/name)
    for name in ['README.md','LICENSE','THIRD_PARTY.md']:
        if (ROOT/name).exists():shutil.copy2(ROOT/name,dest/name)
    (dest/'LocalMeeting.exe').replace(dest/'KhansMinutes.exe')
    print(str(dest/'KhansMinutes.exe'),flush=True)

if __name__=='__main__':main()
