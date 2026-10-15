"""Source-backed schedule checks and durable, explicit user corrections."""
from copy import deepcopy

POLICY = '''
분류 기준:
- 결정 사항: 명시적 승인뿐 아니라 상대방의 수용, 합의된 추진 방향, 담당자의 실행 약속도 포함한다.
  방향은 합의했으나 가격·일정·구현 세부가 미정이면 방향은 결정 사항, 미정인 세부만 미결 사항으로 나눈다.
  단순 감탄·맞장구를 합의로 단정하지 말고 앞뒤 응답과 실행 의사를 함께 확인한다.
- 제안 사항: 아직 상대방이 수용하지 않은 선택지·아이디어 또는 조건부 검토안이다.
  이미 수용한 제안을 제안/결정 두 곳에 반복하지 않는다. 개인 담당 업무는 실행 과제에도 기록할 수 있다.
- 미결 사항: 결정에 필요한 남은 질문·조건이다. 일부 조건 미정만으로 합의한 방향 전체를 미정으로 돌리지 않는다.
- 후속 일정: 이 회의 참석자 사이에 실제로 약속한 후속 만남만 기록한다.
  요일 단독 언급, 과거 만남, 제3자 일정, 가정·질문·거절, 청취 불명확한 문장은 약속의 근거가 아니다.
  확인되지 않은 일정을 '언급이 있다'는 표현으로 우회하여 포함하지 않는다.
당사자 관계:
- 나/저는 그 발언의 화자, 호칭은 실제 지칭 상대에 연결한다. 정체가 불분명하면 추정하지 않는다.
- 계약·수금·지급·업무 위임은 각각 '누가 → 누구에게 → 무엇을' 하는지 분리한다.
  '상대방 회사', '기술 담당 측'처럼 당사자를 숨기는 표현 대신 확인된 참석자 ID를 쓴다.
- 사용자 확인 사항은 원문 전사를 변경하지 않고 요약 해석에 우선 적용한다.
근거:
- 각 원문 행은 [R번호]로 식별된다. follow_up 각 항목에는 schedule_evidence를 작성한다.
  형식: {"follow_up_index":0,"text":"follow_up의 항목과 동일한 문장","status":"agreed",
  "proposal":{"row":0,"quote":"만남 제안 원문 그대로"},
  "acceptance":{"row":1,"quote":"상대방 동의 원문 그대로"}}
- proposal과 acceptance는 서로 다른 참석자의 실제 행이어야 한다. row는 R 뒤 정수이다.
  quote는 해당 원문에 실제 존재하는 연속 문구이며 앞뒤 문맥의 부정·조건을 제외하지 않는다.
  근거가 없으면 follow_up과 schedule_evidence는 []이다. 근거 번호나 인용문을 만들지 않는다.
- 부분 요약 통합 시 이미 확보한 schedule_evidence의 원문 번호·인용을 그대로 보존한다.
  출력은 간결하게 작성하며 모든 항목에 원문을 반복 인용하지 않는다.
'''


def apply_policy(minutes, rows, review=None):
    """Reject untraceable schedules; keep corrections separate from ASR records.

    Quote matching checks provenance, not the truth of a speech recognizer or
    every semantic interpretation. Human review remains possible via sidecar.
    """
    result=deepcopy(minutes);review=review or {};audit=[]
    evidence=result.pop('schedule_evidence',[])
    accepted=[]
    def source(ref):
        if not isinstance(ref,dict):return None
        index=ref.get('row');quote=ref.get('quote')
        if type(index) is not int or not 0<=index<len(rows):return None
        row=rows[index]
        if not isinstance(quote,str) or not quote.strip() or quote not in row['text']:return None
        if any(marker in row['text'] for marker in ('청취 불명확','확인 필요')):return None
        if not row['speaker'].startswith('참석자') or not row['speaker'][3:].isdigit():return None
        return row
    for item in result.get('follow_up',[]):
        valid=False
        rejected=any(term in item for term in review.get('rejected_schedule_terms',[]))
        if not rejected:
            for proof in evidence:
                if not isinstance(proof,dict) or proof.get('text')!=item or proof.get('status')!='agreed' or proof.get('semantic_verified') is not True:continue
                proposal=source(proof.get('proposal'));acceptance=source(proof.get('acceptance'))
                # Distant, unrelated affirmations cannot validate a schedule.
                if proposal and acceptance and proposal['speaker']!=acceptance['speaker']:
                    gap=acceptance['start']-proposal['start']
                    if 0<=gap<=120:
                        valid=True;break
        if valid:accepted.append(item)
        else:audit.append(dict(section='follow_up',text=item,reason='user_correction' if rejected else 'missing_agreement_evidence'))
    result['follow_up']=accepted
    for correction in review.get('relation_corrections',[]):
        section=correction.get('section');terms=correction.get('match_all',[]);replacement=correction.get('text')
        if section!='discussion' or not terms or not isinstance(replacement,str):continue
        items=result.setdefault(section,[])
        matches=[i for i,item in enumerate(items) if all(term in item for term in terms)]
        if matches:
            for i in reversed(matches[1:]):items.pop(i)
            items[matches[0]]=replacement
        else:items.append(replacement)
        audit.append(dict(section=section,text=replacement,reason='user_confirmed_relation'))
    return result,dict(schedule_evidence=evidence,checks=audit)
