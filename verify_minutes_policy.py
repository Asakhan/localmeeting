from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import settings,atomic_json
from summarize import LocalLLM
from minutes_policy import apply_policy
folder=Path(__file__).resolve().parent/'test-output/minutes-policy-check';folder.mkdir(parents=True,exist_ok=True)
rows=[
dict(start=0,speaker='참석자1',text='호수님 회사가 고객과 계약해서 먼저 대금을 받고, 호수님이 저한테 기술 업무 대금을 주시면 됩니다.'),
dict(start=10,speaker='참석자2',text='네, 제가 고객과 계약하고 받은 다음 대표님께 지급하는 걸로 하겠습니다.'),
dict(start=20,speaker='참석자1',text='초기 개발비 없이 최소 1년 월 운영료 방식으로 추진하죠. 금액은 고객별로 나중에 정하고요.'),
dict(start=30,speaker='참석자2',text='그렇게 하죠. 제가 오늘 소개 자료를 만들어 배포하겠습니다.'),
dict(start=40,speaker='참석자1',text='지난 토요일에는 다른 회사 사람을 만났어요. 이번 토요일에 만나자는 뜻은 아닙니다.'),
dict(start=50,speaker='참석자2',text='우리 다음 회의는 다음 주 화요일에 결과 검토로 할까요?'),
dict(start=60,speaker='참석자1',text='네, 다음 주 화요일에 만나서 결과를 검토합시다.')]
context='회의 시작: 2026-10-15\n사용자가 확인한 이름: 참석자1=문근영, 참석자2=강호수. 출력 ID는 유지하세요.\n'
text=context+'\n'.join(f"[R{i}] {r['speaker']}: {r['text']}" for i,r in enumerate(rows))
started=time.monotonic()
with LocalLLM(folder,settings()) as llm:
    raw=llm.summarize(text)
    llm.review_classification(raw)
    llm.verify_schedules(raw,rows)
result,audit=apply_policy(raw,rows)
atomic_json(folder/'result.json',dict(minutes=result,audit=audit,seconds=time.monotonic()-started))
assert result['decisions'],result
assert any('1년' in x.replace(' ','') for x in result['decisions']),result
assert any('금액' in x for x in result['unresolved']),result
assert not any('1년' in x.replace(' ','') for x in result['suggestions']),result
assert all('토요일' not in x for x in result['follow_up']),result
assert any('화요일' in x for x in result['follow_up']),result
print(json.dumps(result,ensure_ascii=False))
