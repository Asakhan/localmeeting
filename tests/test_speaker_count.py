import unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from core import estimated_speakers
from engine import SpeechEngine


def unit(*v):
    v=np.asarray(v,dtype=np.float32);return v/np.linalg.norm(v)


def engine(count=0):
    e=SpeechEngine.__new__(SpeechEngine)
    e.np=np;e.config={'speaker_threshold':.65,'speaker_count':count};e.centroids=[]
    return e


class LiveSpeakerTests(unittest.TestCase):
    def test_unknown_count_still_creates_new_voice(self):
        e=engine()
        self.assertEqual(e.speaker(unit(1,0,0,0),'mic'),'참석자1')
        self.assertEqual(e.speaker(unit(0,1,0,0),'mic'),'참석자2')

    def test_known_count_caps_live_identities(self):
        # 2026-11-11: a 3-person meeting produced 14 live centroids.
        e=engine(3)
        for i,v in enumerate([(1,0,0,0),(0,1,0,0),(0,0,1,0)]):
            self.assertEqual(e.speaker(unit(*v),'mic'),f'참석자{i+1}')
        self.assertEqual(e.speaker(unit(.2,.1,.1,1),'mic'),'참석자1')
        self.assertEqual(len(e.centroids),3)

    def test_cap_respects_excluded_labels(self):
        e=engine(2)
        e.speaker(unit(1,0,0),'mic');e.speaker(unit(0,1,0),'mic')
        self.assertEqual(e.speaker(unit(.9,.1,0),'mic',excluded=['참석자1']),'참석자2')
        self.assertEqual(e.speaker(unit(0,0,1),'mic',excluded=['참석자1','참석자2']),'화자 미확인')

    def test_cap_is_per_source(self):
        e=engine(1)
        self.assertEqual(e.speaker(unit(1,0),'mic'),'참석자1')
        self.assertEqual(e.speaker(unit(0,1),'system'),'참석자2')


class DisplayedCountTests(unittest.TestCase):
    def test_fragments_are_not_counted_as_participants(self):
        rows=[dict(start=0,end=600,speaker='참석자4'),dict(start=600,end=1000,speaker='참석자3'),
              dict(start=1000,end=1200,speaker='참석자6'),dict(start=1200,end=1202,speaker='참석자13'),
              dict(start=1202,end=1203,speaker='참석자14'),dict(start=1203,end=1210,speaker='화자 미확인')]
        self.assertEqual(estimated_speakers(rows),3)

    def test_short_meeting_counts_real_turns(self):
        rows=[dict(start=0,end=30,speaker='참석자1'),dict(start=30,end=60,speaker='참석자2')]
        self.assertEqual(estimated_speakers(rows),2)


if __name__=='__main__':unittest.main()
