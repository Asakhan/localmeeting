import unittest,tempfile
from pathlib import Path
from core import atomic_json,append_jsonl,export_docx,export_minutes_text,empty_minutes,validate_minutes
from minutes_policy import apply_policy
from summarize import LocalLLM


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.rows=[dict(start=0,speaker='참석자1',text='다음 주 화요일에 결과 검토 회의를 하죠.'),
                   dict(start=5,speaker='참석자2',text='네, 화요일에 만나서 결과를 검토하겠습니다.')]
        self.item='다음 주 화요일 결과 검토 회의'
        self.proof=dict(text=self.item,status='agreed',semantic_verified=True,
                        proposal=dict(row=0,quote=self.rows[0]['text']),acceptance=dict(row=1,quote=self.rows[1]['text']))
    def run_policy(self,review=None):
        return apply_policy(dict(empty_minutes(),follow_up=[self.item],schedule_evidence=[self.proof]),self.rows,review)[0]
    def test_confirmed_schedule(self):self.assertEqual(self.run_policy()['follow_up'],[self.item])
    def test_mention_is_not_agreement(self):
        self.proof['status']='mentioned';self.assertEqual(self.run_policy()['follow_up'],[])
    def test_semantic_review_required(self):
        self.proof.pop('semantic_verified');self.assertEqual(self.run_policy()['follow_up'],[])
    def test_fake_quote_rejected(self):
        self.proof['acceptance']['quote']='그렇게 합시다.';self.assertEqual(self.run_policy()['follow_up'],[])
    def test_self_acceptance_rejected(self):
        self.rows[1]['speaker']='참석자1';self.assertEqual(self.run_policy()['follow_up'],[])
    def test_unclear_context_rejected(self):
        self.rows[0]['text']+=' [청취 불명확]';self.assertEqual(self.run_policy()['follow_up'],[])
    def test_unrelated_later_agreement_rejected(self):
        self.rows[1]['start']=900;self.assertEqual(self.run_policy()['follow_up'],[])
    def test_user_correction_overrides_model(self):
        self.assertEqual(self.run_policy({'rejected_schedule_terms':['화요일']})['follow_up'],[])
    def test_bad_row_reference_rejected(self):
        self.proof['acceptance']['row']=999;self.assertEqual(self.run_policy()['follow_up'],[])
    def test_verified_relation_survives_regeneration(self):
        raw=dict(empty_minutes(),discussion=['상대방 회사가 계약하고 기술 담당에게 지급한다.'])
        review={'relation_corrections':[dict(section='discussion',match_all=['계약','지급'],text='참석자2가 계약·수금 후 참석자1에게 지급한다.')]}
        result,_=apply_policy(raw,self.rows,review)
        self.assertEqual(result['discussion'],[review['relation_corrections'][0]['text']])
        self.assertEqual(raw['discussion'],['상대방 회사가 계약하고 기술 담당에게 지급한다.'])
    def test_evidence_survives_partial_summary_validation(self):
        self.assertEqual(validate_minutes(dict(empty_minutes(),schedule_evidence=[self.proof]))['schedule_evidence'],[self.proof])
    def test_semantic_verifier_can_reject_exact_quotes(self):
        llm=LocalLLM('.',{})
        llm.request=lambda *a,**kw:{'choices':[dict(finish_reason='stop',message=dict(content='{"confirmed":false,"reason":"다른 안건에 대한 맞장구"}'))]}
        minutes=dict(follow_up=[self.item],schedule_evidence=[self.proof])
        llm.verify_schedules(minutes,self.rows)
        self.assertFalse(self.proof['semantic_verified'])


class SummaryExportTests(unittest.TestCase):
    def test_summary_has_names_and_no_transcript_appendix(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            atomic_json(folder/'meeting.json',dict(started='2026-10-15',ended='2026-10-15'))
            atomic_json(folder/'names.json',{'참석자1':'문근영','참석자2':'강호수'})
            atomic_json(folder/'minutes.json',dict(empty_minutes(),note='참석자1·참석자2',discussion=['참석자2가 고객 대금을 수령한 뒤 참석자1에게 지급한다.']))
            append_jsonl(folder/'transcript.jsonl',dict(start=0,end=1,speaker='참석자1',text='부록에 들어가면 안 되는 원문'))
            doc=Document(export_docx(folder));text='\n'.join(p.text for p in doc.paragraphs)
            summary=export_minutes_text(folder).read_text(encoding='utf-8-sig')
            for output in (text,summary):
                self.assertNotIn('발언 기록',output);self.assertNotIn('부록에 들어가면 안 되는 원문',output)
                self.assertIn('강호수가 고객 대금을 수령한 뒤 문근영에게 지급',output)
                self.assertIn('문근영·강호수',output);self.assertNotIn('참석자1',output)

if __name__=='__main__':unittest.main()
