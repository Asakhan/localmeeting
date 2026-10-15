import tempfile
import unittest
from pathlib import Path
from core import read_json
from fast_correction import correct_fast,make_kiwi,preserves_grammar_facts
from diarization import cluster_voices


class FastPipelineTests(unittest.TestCase):
    def test_model_cannot_change_units_style_or_finish_a_sentence(self):
        kiwi=make_kiwi('')
        for old,new in [('만명의','만 개의'),('됐어','됐어요'),('번역이','번역이죠'),
                        ('한번','한'),('한달에','한 달에에'),('갖다치고','갖다 버리고'),
                        ('말씀해주신','말씀해신')]:
            self.assertFalse(preserves_grammar_facts(old,new,kiwi),(old,new))
    def test_clustering_separates_two_voices_and_stabilizes_ids(self):
        self.assertEqual(cluster_voices([[1.,0.],[.99,.01],[0.,1.],[.01,.99]]),[0,0,1,1])
        self.assertEqual(cluster_voices([[1.,0.],[.8,.2],[0.,1.]],2),[0,0,1])

    def test_spectral_cluster_large_sample(self):
        import numpy as np
        rng=np.random.default_rng(4)
        v=np.concatenate([rng.normal([1.,0.],.03,(40,2)),rng.normal([0.,1.],.03,(40,2))])
        v/=np.linalg.norm(v,axis=1,keepdims=True)
        labels=cluster_voices(v)
        self.assertEqual(len(set(labels)),2)
        self.assertEqual(len(set(labels[:40])),1)
        self.assertNotEqual(labels[0],labels[-1])

    def test_fast_correction_preserves_facts_names_and_loanwords(self):
        texts=['컨택을 했더라고요', '위팅은 저희 제품 이름입니다.',
               '아사검은 3시에 하지 않습니다. [청취 불명확]',
               '할수 있습니다.', '생명은 소중합니다.']
        rows=[dict(text=t,start=i,end=i+1,speaker='참석자1') for i,t in enumerate(texts)]
        with tempfile.TemporaryDirectory() as tmp:
            output=correct_fast(Path(tmp),rows,'위팅')
            self.assertEqual(output[0]['text'],texts[0])
            self.assertEqual(output[1]['text'],texts[1])
            self.assertEqual(output[2]['text'],texts[2])
            self.assertEqual(output[3]['text'],'할 수 있습니다.')
            self.assertEqual(output[4]['text'],texts[4])
            self.assertEqual(output,correct_fast(Path(tmp),output,'위팅'))
            self.assertEqual(read_json(Path(tmp)/'transcript_corrections.json')['reviewed_rows'],5)

    def test_distinct_local_speakers_cannot_merge(self):
        import numpy as np
        from engine import SpeechEngine
        engine=SpeechEngine.__new__(SpeechEngine)
        engine.np=np;engine.centroids=[];engine.config={'speaker_threshold':.65}
        first=engine.speaker(np.array([1.,0.]),'mic')
        second=engine.speaker(np.array([.9,.1]),'mic',[first])
        self.assertNotEqual(first,second)


if __name__=='__main__':unittest.main()
