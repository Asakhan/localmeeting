import unittest, tempfile
from pathlib import Path
from unittest.mock import Mock
from transcript_correction import apply_edits, correct_transcript, phonetic_close
from core import transcript, read_json, recognition_glossary

class CorrectionTests(unittest.TestCase):
    def test_builtin_terms_survive_existing_empty_preferences(self):
        self.assertIn('아사검',recognition_glossary(''))
        self.assertIn('사용자용어',recognition_glossary('사용자용어'))
        self.assertEqual(recognition_glossary('아사검').split(', ').count('아사검'),1)
    def test_grammar_fix_with_protected_name_inside_sentence(self):
        before='아사검의 회의로운 프로그램이 성능이 좋다'
        after='아사검의 회의록은 프로그램의 성능이 좋다'
        output,audit=apply_edits([dict(text=before)],[dict(row=0,before=before,after=after)],recognition_glossary())
        self.assertEqual(output[0]['text'],after)
        self.assertEqual(len(audit),1)
    def test_name_restore_and_protection(self):
        before='아사범의 회의록';after='아사검의 회의록'
        self.assertEqual(apply_edits([dict(text=before)],[dict(row=0,before=before,after=after)],recognition_glossary())[0][0]['text'],after)
        self.assertEqual(apply_edits([dict(text=after)],[dict(row=0,before='사검',after='사범')],recognition_glossary())[0][0]['text'],after)
    def test_long_rewrite_cannot_change_facts(self):
        for before,after in [('회의는 3시에 끝납니다.','회의는 4시에 끝납니다.'),('후속 회의는 없습니다.','후속 회의는 있습니다.'),('김민수가 발표합니다.','이철수가 발표합니다.')]:
            self.assertEqual(apply_edits([dict(text=before)],[dict(row=0,before=before,after=after)])[0][0]['text'],before)
    def test_reported_phonetic_errors(self):
        rows=[dict(text='화자는 반드시 생명으로만 나와야 되겠죠',speaker='참석자1',start=0,end=3),
              dict(text='후속위팅은 없습니다.',speaker='참석자1',start=3,end=5)]
        output,audit=apply_edits(rows,[dict(row=0,before='생명',after='한명'),dict(row=1,before='위팅',after='미팅')])
        self.assertEqual(output[0]['text'],'화자는 반드시 한명으로만 나와야 되겠죠')
        self.assertEqual(output[1]['text'],'후속미팅은 없습니다.')
        self.assertEqual(output[0]['raw_text'],rows[0]['text'])
        self.assertEqual(output[1]['start'],3)
        self.assertEqual(len(audit),2)
    def test_reject_unrelated_rewrite_numbers_negation_and_glossary(self):
        for before,after,glossary in [('회의','여행',''),('3명','1명',''),('없습니다','있습니다',''),('위팅','미팅','위팅')]:
            rows=[dict(text=before)]
            self.assertEqual(apply_edits(rows,[dict(row=0,before=before,after=after)],glossary)[0],rows)
    def test_no_global_word_replacement(self):
        rows=[dict(text='생명은 소중합니다.')]
        self.assertEqual(apply_edits(rows,[])[0],rows)
        named=[dict(text='위팅은 저희 제품 이름입니다.')]
        self.assertEqual(apply_edits(named,[dict(row=0,before='위팅',after='미팅')])[0],named)
    def test_invalid_or_ambiguous_edits(self):
        rows=[dict(text='위팅 위팅')]
        self.assertEqual(apply_edits(rows,[dict(row=0,before='위팅',after='미팅'),dict(row=-1,before='위팅',after='미팅')])[0],rows)
    def test_retry_and_audit(self):
        rows=[dict(text='후속위팅은 없습니다.',speaker='참석자1',start=0,end=2)]
        llm=Mock();llm.correct.return_value=[dict(row=0,before='위팅',after='미팅')]
        llm.correct_grammar.return_value=[]
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            first=correct_transcript(folder,rows,llm)
            second=correct_transcript(folder,first,llm)
            self.assertEqual(first,second)
            self.assertEqual(transcript(folder),second)
            self.assertEqual(len(read_json(folder/'transcript_corrections.json')['edits']),1)
    def test_failure_keeps_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'transcript.jsonl';path.write_text('original',encoding='utf-8')
            llm=Mock();llm.correct.side_effect=ValueError('bad response')
            with self.assertRaises(ValueError):correct_transcript(folder,[dict(text='위팅')],llm)
            self.assertEqual(path.read_text(encoding='utf-8'),'original')
    def test_grammar_pass_keeps_first_raw_text(self):
        raw='아사범의 회의록은 프로그램이 성능이 좋다'
        llm=Mock()
        llm.correct.return_value=[dict(row=0,before='아사범',after='아사검')]
        llm.correct_grammar.return_value=[dict(row=0,before='프로그램이 성능이',after='프로그램의 성능이')]
        with tempfile.TemporaryDirectory() as tmp:
            output=correct_transcript(Path(tmp),[dict(text=raw)],llm)
            self.assertEqual(output[0]['text'],'아사검의 회의록은 프로그램의 성능이 좋다')
            self.assertEqual(output[0]['raw_text'],raw)
            self.assertIn('아사검',llm.correct_grammar.call_args.args[0])
    def test_grammar_does_not_polish_style(self):
        llm=Mock();llm.correct.return_value=[]
        llm.correct_grammar.return_value=[dict(row=0,before='나와야 되겠죠',after='나와야 하겠죠',reason='문어체 통일')]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(correct_transcript(Path(tmp),[dict(text='나와야 되겠죠')],llm)[0]['text'],'나와야 되겠죠')
