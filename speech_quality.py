"""Check acoustic/timing evidence, never blacklist particular Korean words."""
import math, re

def speech_overlap(start,end,regions,padding=0.08):
    spans=sorted((max(start,a-padding),min(end,b+padding)) for a,b in regions
                 if min(end,b+padding)>max(start,a-padding))
    total=0.;right=start
    for a,b in spans:
        total+=max(0.,b-max(right,a));right=max(right,b)
    return total

def word_rejection(word,regions,audio_duration):
    start,end=float(word.start),float(word.end)
    if not math.isfinite(start+end) or start<-.02 or end>audio_duration+.1:
        return 'outside_audio'
    lexical=re.sub(r'\W','',word.word,flags=re.UNICODE)
    duration=end-start
    if lexical and duration<.015:return 'zero_duration'
    if duration<0:return 'reversed_time'
    if lexical and len(lexical)>=3:
        hangul=len(re.findall(r'[가-힣]',lexical))
        if (hangul>=2 and hangul/max(duration,.001)>30) or len(lexical)/max(duration,.001)>65:
            return 'implausible_alignment'
    if lexical and speech_overlap(start,end,regions)<min(.04,duration*.25):
        return 'outside_speech'
    probability=float(getattr(word,'probability',1.))
    if lexical and (not math.isfinite(probability) or probability<.15):return 'low_confidence'
    return None

def speaker_for_word(word,turns,mapping):
    """Adjacent turns from the same voice are not overlapping speakers."""
    overlaps={}
    for turn in turns:
        speaker=mapping[turn.speaker]
        overlap=max(0.,min(word.end,turn.end)-max(word.start,turn.start))
        overlaps[speaker]=overlaps.get(speaker,0.)+overlap
    if not overlaps or max(overlaps.values())<=0:return '화자 미확인'
    candidates=[s for s,o in overlaps.items() if o>max(.04,(word.end-word.start)*.4)]
    # Require actually simultaneous intervals belonging to different voices.
    if len(candidates)>1:
        for i,a in enumerate(turns):
            for b in turns[i+1:]:
                if mapping[a.speaker]!=mapping[b.speaker] and min(word.end,a.end,b.end)-max(word.start,a.start,b.start)>.08:
                    return '겹침 발화'
    return max(overlaps,key=overlaps.get)
