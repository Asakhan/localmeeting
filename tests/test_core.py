import unittest, tempfile, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import (atomic_json, append_jsonl, display, empty_minutes, finalize_outputs,
                  transcript, read_json, export_docx, export_text, validate_minutes)

class MeetingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'audio').mkdir();(self.root/'results').mkdir()
        atomic_json(self.root/'meeting.json',dict(started='2026-10-15T10:00:00+09:00',ended='2026-10-15T10:30:00+09:00'))
        atomic_json(self.root/'capture_done.json',dict(errors=[]))
        atomic_json(self.root/'minutes.json',dict(empty_minutes(),title='개발 회의',decisions=['참석자1과 참석자10이 승인했다.']))
        append_jsonl(self.root/'transcript.jsonl',dict(start=0,end=1,speaker='참석자1',text='금요일까지 검토하겠습니다.'))
    def tearDown(self):self.tmp.cleanup()
    def audio(self):
        (self.root/'audio'/'mic_000.wav').write_bytes(b'test audio')
        atomic_json(self.root/'audio'/'mic_000.json',dict(file='mic_000.wav'))
    def test_names_are_not_cascading(self):
        self.assertEqual(display('참석자1 참석자10 참석자2',{'참석자1':'참석자2','참석자2':'김철수','참석자10':'이영희'}),'참석자2 이영희 김철수')
    def test_delete_only_after_completed_outputs(self):
        self.audio();atomic_json(self.root/'results'/'mic_000.json',dict(rows=[]))
        doc=finalize_outputs(self.root)
        self.assertTrue(doc.exists());self.assertTrue((self.root/'전체전사.txt').exists())
        self.assertFalse(list((self.root/'audio').iterdir()))
        self.assertTrue(read_json(self.root/'meeting.json')['audio_deleted'])
    def test_incomplete_transcription_keeps_audio(self):
        self.audio();finalize_outputs(self.root)
        self.assertTrue((self.root/'audio'/'mic_000.wav').exists())
        self.assertFalse(read_json(self.root/'meeting.json')['audio_deleted'])
    def test_capture_error_keeps_audio(self):
        self.audio();atomic_json(self.root/'results'/'mic_000.json',{})
        atomic_json(self.root/'capture_done.json',dict(errors=['device disconnected']))
        finalize_outputs(self.root)
        self.assertTrue((self.root/'audio'/'mic_000.wav').exists())
    def test_orphan_audio_is_never_deleted(self):
        (self.root/'audio'/'orphan.wav').write_bytes(b'audio')
        finalize_outputs(self.root)
        self.assertTrue((self.root/'audio'/'orphan.wav').exists())
    def test_incomplete_tail_keeps_audio(self):
        (self.root/'audio'/'mic_1.part.wav').write_bytes(b'x')
        finalize_outputs(self.root)
        self.assertTrue((self.root/'audio'/'mic_1.part.wav').exists())
    def test_rename_updates_both_exports(self):
        from docx import Document
        atomic_json(self.root/'names.json',{'참석자1':'김민수','참석자10':'이영희'})
        export_text(self.root);doc=Document(export_docx(self.root))
        text='\n'.join(p.text for p in doc.paragraphs)
        self.assertIn('김민수과 이영희',text)
        self.assertIn('김민수:',(self.root/'전체전사.txt').read_text(encoding='utf-8-sig'))
        self.assertEqual(transcript(self.root)[0]['speaker'],'참석자1')
    def test_schema_rejects_invalid_actions(self):
        with self.assertRaises(ValueError):validate_minutes(dict(title='회의',actions=['담당자 없음']))
    def test_trailing_interrupted_jsonl(self):
        with (self.root/'transcript.jsonl').open('a',encoding='utf-8') as f:f.write('{"broken":')
        self.assertEqual(len(transcript(self.root)),1)
    def test_llm_spaced_speaker_ids_are_normalized(self):
        data=validate_minutes(dict(title='회의',actions=[dict(owner='참석자 2',due='미정',task='검토')]))
        self.assertEqual(data['actions'][0]['owner'],'참석자2')
    def test_zero_duration_hallucination_is_rejected(self):
        from engine import credible_segment
        from types import SimpleNamespace
        self.assertFalse(credible_segment(SimpleNamespace(start=3.48,end=3.50,text='아버지 뭐하시노.')))
        self.assertTrue(credible_segment(SimpleNamespace(start=3,end=3.2,text='네.')))

if __name__=='__main__':unittest.main()
