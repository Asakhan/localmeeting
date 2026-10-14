"""Frozen EXE integration test; public fixture audio only. Models run sequentially."""
from pathlib import Path
import subprocess, time, json, shutil, os, psutil
from core import ROOT,settings,atomic_json,read_json

def main():
    exe=ROOT/'dist/LocalMeeting/LocalMeeting.exe'
    folder=ROOT/'test-output/exe-meeting';folder.mkdir(parents=True,exist_ok=True)
    audio=folder/'audio';audio.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'test-output/ko.wav',audio/'mic_0000000.wav')
    atomic_json(audio/'mic_0000000.json',dict(source='mic',offset=0,duration=3.5265,file='mic_0000000.wav'))
    config=settings();config['model_root']=str(exe.parent/'models')
    atomic_json(folder/'meeting.json',dict(started='2026-10-15T10:00:00+09:00',ended='2026-10-15T10:00:04+09:00',config=config))
    atomic_json(folder/'capture_done.json',dict(errors=[]))
    metrics=[]
    for stage in ['transcribe','summarize']:
        start=time.perf_counter();peak_rss=0;peak_gpu=0;cpu_time=0
        process=subprocess.Popen([str(exe),'--'+stage,str(folder)],creationflags=subprocess.CREATE_NO_WINDOW)
        tracked={}
        while process.poll() is None:
            try:
                parent=psutil.Process(process.pid);children=[parent]+parent.children(recursive=True)
                memory=0
                for child in children:
                    try:
                        memory+=child.memory_info().rss;t=child.cpu_times();tracked[child.pid]=t.user+t.system
                    except psutil.Error:pass
                peak_rss=max(peak_rss,memory)
                p=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
                peak_gpu=max(peak_gpu,int(p.stdout.strip().splitlines()[0]))
            except (psutil.Error,ValueError):pass
            time.sleep(.3)
        elapsed=time.perf_counter()-start
        metrics.append(dict(stage=stage,exit_code=process.returncode,seconds=elapsed,peak_rss_gib=peak_rss/2**30,gpu_total_peak_mib=peak_gpu,cpu_seconds=sum(tracked.values()),machine_cpu_mean_percent=sum(tracked.values())/elapsed/os.cpu_count()*100))
        print(json.dumps(metrics[-1]),flush=True)
        if process.returncode:
            print(read_json(folder/'worker_status.json'),flush=True);raise SystemExit(process.returncode)
    atomic_json(ROOT/'test-output/exe_metrics.json',metrics)
    assert (folder/'회의록.docx').exists()
    assert (folder/'전체전사.txt').exists()
    assert not list(audio.glob('*.wav')), 'Audio must be deleted after success'
    print('EXE END-TO-END PASS',flush=True)

if __name__=='__main__':main()
