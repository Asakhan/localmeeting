"""Integration check using explicit synthetic transcript, never microphone data."""
from pathlib import Path
import time, json
from core import ROOT,settings,atomic_json,append_jsonl
from summarize import run_summary

if __name__=='__main__':
    root=ROOT/'test-output'/'summary';root.mkdir(parents=True,exist_ok=True)
    (root/'audio').mkdir(exist_ok=True);(root/'results').mkdir(exist_ok=True)
    config=settings();config['model_root']=str(ROOT/'models')
    atomic_json(root/'meeting.json',dict(started='2026-10-15T10:00:00+09:00',ended='2026-10-15T10:30:00+09:00',config=config))
    atomic_json(root/'capture_done.json',dict(errors=[]))
    (root/'transcript.jsonl').write_text('',encoding='utf-8')
    lines=[('참석자1','오늘은 홈페이지 개편 일정과 예산을 논의하겠습니다. 디자인 시안을 다음 주 화요일까지 만들어 주세요.'),
           ('참석자2','제가 디자인 시안을 다음 주 화요일까지 만들겠습니다. 고객 인터뷰를 세 명 정도 진행하는 것도 제안합니다.'),
           ('참석자1','디자인 일정은 그렇게 확정합시다. 고객 인터뷰는 아직 승인하지 않고 다음 회의에서 논의하겠습니다.'),
           ('참석자2','예산은 삼백만 원이 필요합니다.'),
           ('참석자1','예산 삼백만 원 집행을 승인합니다. 다음 회의는 10월 22일 오후 두 시에 합시다.'),
           ('참석자2','네, 참석하겠습니다.')]
    for i,(speaker,text) in enumerate(lines):append_jsonl(root/'transcript.jsonl',dict(start=i*20,end=i*20+15,speaker=speaker,text=text,source='mic'))
    start=time.perf_counter();code=run_summary(root)
    print(json.dumps(dict(exit_code=code,seconds=time.perf_counter()-start),ensure_ascii=False),flush=True)
    print((root/'worker_status.json').read_text(encoding='utf-8'),flush=True)
    if (root/'minutes.json').exists():print((root/'minutes.json').read_text(encoding='utf-8'),flush=True)
    raise SystemExit(code)
