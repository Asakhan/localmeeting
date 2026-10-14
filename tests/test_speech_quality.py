import unittest,sys
import tempfile
from unittest.mock import patch, Mock
from pathlib import Path
from types import SimpleNamespace as S
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from speech_quality import word_rejection,speaker_for_word

def word(text,start=1.,end=1.8,prob=.95):return S(word=text,start=start,end=end,probability=prob)

class EvidenceTests(unittest.TestCase):
    def test_process_rejects_unaligned_decoder_sentence(self):
        import numpy as np
        import soundfile as sf
        from engine import SpeechEngine
        engine=SpeechEngine.__new__(SpeechEngine)
        engine.np=np;engine.config={'language':'ko'}
        segment=S(start=0.,end=1.,text='없는 문장',words=[],no_speech_prob=.01,avg_logprob=-.1)
        engine.whisper=Mock()
        engine.whisper.transcribe.return_value=([segment],None)
        engine.diarizer=Mock()
        engine.diarizer.process.return_value.sort_by_start_time.return_value=[]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'audio.wav';sf.write(path,np.zeros(16000),16000)
            with patch('faster_whisper.vad.get_speech_timestamps',return_value=[{'start':0,'end':16000}]):
                self.assertEqual(engine.process(path,{'source':'mic','offset':0}),[])
        self.assertEqual(engine.last_quality['rejected'][0]['reason'],'missing_alignment')

    def test_zero_length_tail_inside_long_segment(self):
        # Must reject word-level suffix even if the surrounding segment is many seconds.
        self.assertEqual(word_rejection(word('질문해',11.33,11.33),[(0,11.4)],12),'zero_duration')
    def test_fast_tail_not_caught_by_old_eighty_ms_filter(self):
        self.assertEqual(word_rejection(word('주시겠어요?아버지 뭐하시노.',11.33,11.47),[(0,11.5)],12),'implausible_alignment')
    def test_words_outside_actual_speech(self):
        self.assertEqual(word_rejection(word('은혜',8,8.7),[(0,3)],12),'outside_speech')
    def test_uncertain_word_not_published_as_fact(self):
        self.assertEqual(word_rejection(word('헬미',prob=.1),[(0,5)],12),'low_confidence')
    def test_no_word_blacklist(self):
        for text in ['테스트','게스트','은혜','헬미','아버지 뭐하시노.']:
            self.assertIsNone(word_rejection(word(text,1,3),[(0,5)],12),text)
    def test_short_real_acknowledgement_is_retained(self):
        self.assertIsNone(word_rejection(word('네',1,1.08),[(0,3)],12))
    def test_same_speaker_turns_not_marked_as_overlap(self):
        turns=[S(start=0,end=1.5,speaker=0),S(start=1.2,end=3,speaker=0)]
        self.assertEqual(speaker_for_word(word('테스트',1.2,1.7),turns,{0:'참석자1'}),'참석자1')
    def test_adjacent_different_turns_not_overlap(self):
        turns=[S(start=0,end=1.5,speaker=0),S(start=1.5,end=3,speaker=1)]
        self.assertNotEqual(speaker_for_word(word('테스트',1.2,1.8),turns,{0:'참석자1',1:'참석자2'}),'겹침 발화')
    def test_actual_overlapping_voices(self):
        turns=[S(start=0,end=2,speaker=0),S(start=1,end=3,speaker=1)]
        self.assertEqual(speaker_for_word(word('테스트',1.2,1.8),turns,{0:'참석자1',1:'참석자2'}),'겹침 발화')

if __name__=='__main__':unittest.main()
