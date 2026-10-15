"""CPU Korean contextual morphology; no autoregressive full-transcript rewriting."""
import json
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from core import atomic_json, recognition_glossary
from transcript_correction import apply_edits


def make_kiwi(glossary):
    from kiwipiepy import Kiwi
    import kiwipiepy_model
    # Kiwi's Windows native loader cannot open Korean absolute paths. Load all
    # model resources relative to their directory, then restore the worker cwd.
    previous = Path.cwd()
    try:
        os.chdir(Path(kiwipiepy_model.__file__).parent)
        kiwi = Kiwi(model_path='.', num_workers=4, model_type='cong')
        for term in re.split(r'[,;\n]+', glossary):
            for word in term.split():
                if re.fullmatch('[가-힣]+', word):
                    kiwi.add_user_word(word, 'NNP', 0)
        kiwi.tokenize('준비')
    finally:
        os.chdir(previous)
    return kiwi


def preserves_grammar_facts(old,new,kiwi):
    def anchors(text):
        return [(t.form,t.tag) for t in kiwi.tokenize(text)
                if t.tag in ('VV','VA','VX','NNP','NNB','NP','SN','NR','MM','MAG','MAJ')
                or t.tag.startswith(('E','J','X'))
                or t.form in ('명','개','원','시','분','초','년','월','일','배','퍼센트')]
    return anchors(old)==anchors(new)


def grammar_proposals(rows, model_root, deadline, kiwi):
    """Small KoBART GEC model; emit local edits rather than accept rewrites."""
    import ctranslate2
    from tokenizers import Tokenizer
    from engine import gpu_free
    path=Path(model_root)/'kogrammar'
    tokenizer=Tokenizer.from_file(str(path/'tokenizer.json'))
    device='cuda' if gpu_free()>1500 else 'cpu'
    model=ctranslate2.Translator(str(path),device=device,
        compute_type='int8_float16' if device=='cuda' else 'int8',intra_threads=4)
    pieces=[(i,m.group()) for i,row in enumerate(rows)
            for m in re.finditer(r'.{1,180}(?:\s|$)|.{1,180}',row['text'])]
    proposals=[]; reviewed=0
    batch_size=32 if device=='cuda' else 8
    try:
        for first in range(0,len(pieces),batch_size):
            if time.perf_counter()>deadline:break
            batch=pieces[first:first+batch_size]
            inputs=[tokenizer.encode(text).tokens for _,text in batch]
            outputs=model.translate_batch(inputs,beam_size=1,max_decoding_length=200,
                                          end_token=['</s>','<pad>'],return_end_token=True)
            reviewed+=len(batch)
            for (index,before),output in zip(batch,outputs):
                tokens=output.hypotheses[0]
                if not tokens or tokens[-1] not in ('</s>','<pad>'):continue
                after=tokenizer.decode([tokenizer.token_to_id(t) for t in tokens])
                # Align whole words, so a replacement cannot be detached from
                # an adjacent insertion/deletion and leave half a correction.
                source=list(re.finditer(r'[^\s,.!?]+',before))
                target=list(re.finditer(r'[^\s,.!?]+',after))
                for op,a,b,c,d in SequenceMatcher(None,[m.group() for m in source],
                        [m.group() for m in target],autojunk=False).get_opcodes():
                    if op!='replace':continue
                    if b-a>2 or d-c>2:continue
                    old=before[source[a].start():source[b-1].end()]
                    new=after[target[c].start():target[d-1].end()]
                    if not re.fullmatch('[가-힣 ]+',old+new):continue
                    # Lexical verbs, names and numerical counters are facts,
                    # not stylistic grammar. Reject changes to those anchors.
                    if not preserves_grammar_facts(old,new,kiwi):continue
                    proposals.append(dict(row=index,before=old,after=new,reason='KoGrammar 문장 문맥 교정'))
    finally:
        model.unload_model()
    return proposals,dict(device=device,reviewed_chunks=reviewed,total_chunks=len(pieces),
                           complete=reviewed==len(pieces))


def correct_fast(folder, rows, glossary='', model_root=None):
    started = time.perf_counter()
    folder = Path(folder)
    glossary = recognition_glossary(glossary)
    raw = [dict(r, text=r.get('raw_text', r['text'])) for r in rows]
    kiwi = make_kiwi(glossary)
    proposals = []
    # Bound individual native calls without discarding long utterances.
    pieces = [(i, m.start(), m.group()) for i, row in enumerate(raw)
              for m in re.finditer(r'.{1,300}(?:\s|$)|.{1,300}', row['text'])]
    texts = [p[2] for p in pieces]
    for (index, offset, text), tokens in zip(pieces, kiwi.tokenize(
            texts, typos='basic', typo_cost_threshold=1.5)):
        # Reconstruct only typo spans, including conjugated morphemes sharing a
        # span. Never regenerate the whole utterance from normalized morphemes.
        spans = sorted({(t.start, t.end) for t in tokens if t.typo_cost > 0})
        for start, end in spans:
            group = [t for t in tokens if t.start < end and t.end > start]
            if not group or any(t.start < start or t.end > end for t in group):
                continue
            before = text[start:end]
            after = kiwi.join(group)
            proposals.append(dict(row=index, before=before, after=after,
                                   reason='Kiwi 문맥 언어 모델·오타 후보 비교'))
    corrected, edits = apply_edits(raw, proposals, glossary)
    for edit in edits:
        edit['stage'] = 'contextual_typo'
    grammar=dict(complete=False,reason='문장 교정 모델 미지정')
    if model_root is not None:
        proposals,grammar=grammar_proposals(corrected,model_root,started+50,kiwi)
        corrected,accepted=apply_edits(corrected,proposals,glossary)
        for edit in accepted:edit['stage']='contextual_grammar'
        edits.extend(accepted)
    for i, spaced in enumerate(kiwi.space([r['text'] for r in corrected])):
        before = corrected[i]['text']
        # Avoid fragmenting loanwords (e.g. 컨택 -> 컨 택) or changing connective
        # endings (있는데 -> 있는 데). Only clear bound-noun spacing is automatic.
        safe = before
        changes=[]
        for op,a,b,c,d in SequenceMatcher(None,before,spaced,autojunk=False).get_opcodes():
            if op=='insert' and spaced[c:d]==' ':
                tail=before[a:]
                if a and before[a-1] in '할될갈볼올을는던한된간본온' and re.match(r'(수|것|때)(?:[은는이가을를도에만]?)(?:\s|[.!?,]|$)',tail):
                    changes.append(a)
        for a in reversed(changes):safe=safe[:a]+' '+safe[a:]
        spaced=safe
        # Whitespace changes cannot change names, numbers or uncertainty markers.
        protected = [t.strip() for t in glossary.split(',')] + ['[청취 불명확]', '[확인 필요]']
        if (before != spaced and re.sub(r'\s', '', before) == re.sub(r'\s', '', spaced)
                and all(spaced.count(t) >= before.count(t) for t in protected if t)):
            corrected[i]['text'] = spaced
            corrected[i]['raw_text'] = raw[i]['text']
            edits.append(dict(row=i, before=before, after=spaced,
                              reason='형태소 문맥 기반 띄어쓰기', stage='spacing'))
    atomic_json(folder/'transcript_corrections.json', dict(
        version=2, engine='kiwi-cong+kogrammar' if model_root else 'kiwi-cong', seconds=time.perf_counter()-started,
        grammar=grammar,
        reviewed_rows=len(rows), edits=edits,
        limitation='음성 인식 오류의 완전 복원은 보장하지 않음. 불확실한 변경은 보존.'))
    temp = folder/'transcript.correcting.tmp'
    with temp.open('w', encoding='utf-8') as stream:
        for row in corrected:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, folder/'transcript.jsonl')
    return corrected
