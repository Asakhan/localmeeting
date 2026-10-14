"""WASAPI capture: bounded RAM, incremental WAV, durable chunk handoff."""
from pathlib import Path
import threading, time, shutil, math
import numpy as np
import soundfile as sf
import pyaudiowpatch as pa
from core import atomic_json, now

def devices():
    with pa.PyAudio() as p:
        wasapi=p.get_host_api_info_by_type(pa.paWASAPI)['index']
        return [dict(d) for d in p.get_device_info_generator()
                if d['hostApi']==wasapi and d['maxInputChannels']>0]

class Capture:
    def __init__(self, folder, config):
        self.folder=Path(folder);self.config=config
        self.stop_event=threading.Event();self.threads=[];self.errors=[]
        self.levels={};self.opened=[];self.started=0.;self.last_received={}

    def start(self):
        self.audio=pa.PyAudio()
        try:
            api=self.audio.get_host_api_info_by_type(pa.paWASAPI)
            idx=self.config.get('microphone',-1)
            if idx<0:idx=int(api['defaultInputDevice'])
            sources=[('mic',self.audio.get_device_info_by_index(idx))]
            if self.config.get('system_audio'):
                sources.append(('system',self.audio.get_default_wasapi_loopback()))
            for source,d in sources:
                rate=int(d['defaultSampleRate']);channels=min(2,int(d['maxInputChannels']))
                stream=self.audio.open(format=pa.paInt16,channels=channels,rate=rate,input=True,
                    input_device_index=d['index'],frames_per_buffer=rate//10,start=False)
                self.opened.append((source,stream,rate,channels))
            self.started=time.monotonic()
            for source,stream,rate,channels in self.opened:
                stream.start_stream()
                t=threading.Thread(target=self._record,args=(source,stream,rate,channels),daemon=True)
                self.threads.append(t);t.start()
        except Exception:
            for _,s,_,_ in self.opened:s.close()
            self.audio.terminate();raise

    def _record(self,source,stream,rate,channels):
        sequence=0; frames=0; writer=None; path=None
        try:
            last_packet=time.monotonic()
            while True:
                stopping=self.stop_event.is_set()
                available=stream.get_read_available()
                if available<=0:
                    self.levels[source]=0.
                    if stopping:break
                    if source=='mic' and time.monotonic()-last_packet>5:
                        raise RuntimeError('마이크에서 5초 동안 데이터가 도착하지 않았습니다. 장치 연결을 확인하세요.')
                    # WASAPI loopback emits no packets when the output endpoint is idle.
                    # Never block in read(): stop must remain responsive during silence.
                    if writer and time.monotonic()-last_packet>0.5:
                        writer.close();writer=None
                        self._publish(path,source,offset,frames/rate);sequence+=1
                    self.stop_event.wait(.01);continue
                # Drain the already-buffered tail once when stopping, then exit.
                take=available if stopping else min(available,rate//10)
                if writer is None:
                    if shutil.disk_usage(self.folder).free < 512*1024**2:
                        raise RuntimeError('디스크 여유 공간이 512MB 미만입니다. 녹음을 중단합니다.')
                    path=self.folder/'audio'/f'{source}_{sequence:07}.part.wav'
                    offset=max(0,time.monotonic()-self.started-available/rate)
                    atomic_json(path.with_suffix('.json'),dict(source=source,offset=offset,rate=rate))
                    writer=sf.SoundFile(str(path),mode='w',samplerate=rate,channels=1,subtype='PCM_16')
                    frames=0
                raw=stream.read(take,exception_on_overflow=True)
                last_packet=time.monotonic()
                samples=np.frombuffer(raw,dtype=np.int16).reshape(-1,channels).astype(np.float32).mean(axis=1)/32768
                writer.write(samples);writer.flush()
                self.last_received[source]=time.monotonic()
                self.levels[source]=min(1.,float(np.sqrt(np.mean(samples*samples)))*5)
                frames+=len(samples)
                if frames>=rate*12:
                    writer.close();writer=None
                    self._publish(path,source,offset,frames/rate)
                    sequence+=1
                if stopping:break
        except Exception as e:
            self.errors.append(f'{source}: {e}');self.stop_event.set()
        finally:
            if writer:
                writer.close()
                if frames:self._publish(path,source,offset,frames/rate)
            stream.stop_stream();stream.close()

    def _publish(self,path,source,offset,duration):
        ready=path.with_name(path.name.replace('.part.wav','.wav'))
        path.replace(ready)
        atomic_json(ready.with_suffix('.json'),dict(source=source,offset=offset,duration=duration,file=ready.name))
        path.with_suffix('.json').unlink(missing_ok=True)

    def stop(self):
        self.stop_event.set()
        for thread in self.threads:thread.join(timeout=10)
        if any(t.is_alive() for t in self.threads):
            raise RuntimeError('오디오 장치 종료가 지연됩니다. 원본을 보존했습니다.')
        self.audio.terminate()
        atomic_json(self.folder/'capture_done.json',dict(ended=now(),errors=self.errors))

def recover_partial(folder):
    """Salvage the last incremental WAV after unexpected shutdown."""
    folder=Path(folder)
    for path in (folder/'audio').glob('*.part.wav'):
        from core import read_json
        meta=read_json(path.with_suffix('.json'),{})
        if not meta:continue
        try:
            info=sf.info(str(path))
            if info.frames==0:continue
            ready=path.with_name(path.name.replace('.part.wav','.wav'))
            path.replace(ready)
            atomic_json(ready.with_suffix('.json'),dict(source=meta['source'],offset=meta['offset'],duration=info.duration,file=ready.name))
            path.with_suffix('.json').unlink(missing_ok=True)
        except (OSError,RuntimeError):continue
