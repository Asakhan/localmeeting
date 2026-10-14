"""Run local model correction against reported errors and preservation cases."""
from core import ROOT,settings,atomic_json
from summarize import LocalLLM
from transcript_correction import correct_transcript

def main():
    folder=ROOT/'test-output/correction';folder.mkdir(parents=True,exist_ok=True)
    texts=['지금 저 혼자 말하고 있습니다. 화자는 반드시 생명으로만 나와야 되겠죠',
           '후속위팅은 없습니다.', '생명은 소중합니다.',
           '참석자는 3명이며 다음 회의는 없습니다.', '위팅은 저희 제품 이름입니다.',
           '아사범의 회의록을 테스트합니다.',
           '아사검의 회의로운 프로그램이 성능이 좋다',
           '아사검의 회의록은 프로그램의 성능이 좋다',
           '오늘 회의은 여기서 마치겠습니다.', '프로그램이 좋다']
    rows=[dict(text=text,start=i*5,end=i*5+4,speaker='참석자1',source='mic') for i,text in enumerate(texts)]
    config=settings();config['model_root']=str(ROOT/'models')
    with LocalLLM(folder,config) as llm:
        original_correct=llm.correct
        def capture_proposals(payload,grammar=False):
            edits=original_correct(payload,grammar=grammar)
            atomic_json(folder/('grammar_proposals.json' if grammar else 'proposals.json'),edits)
            return edits
        llm.correct=capture_proposals
        output=correct_transcript(folder,rows,llm)
    atomic_json(folder/'verification.json',output)
    assert '한명' in output[0]['text'].replace(' ',''),output[0]
    assert '나와야 되겠죠' in output[0]['text'],output[0]
    assert '후속미팅' in output[1]['text'].replace(' ',''),output[1]
    for index in [2,3,4]:assert output[index]['text']==texts[index],output[index]
    assert output[5]['text']=='아사검의 회의록을 테스트합니다.',output[5]
    assert output[6]['text']=='아사검의 회의록은 프로그램의 성능이 좋다',output[6]
    assert output[7]['text']==texts[7],output[7]
    assert output[8]['text']=='오늘 회의는 여기서 마치겠습니다.',output[8]
    assert output[9]['text']==texts[9],output[9]
    print('LOCAL CORRECTION PASS',flush=True)

if __name__=='__main__':main()
