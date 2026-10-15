"""Final recording-wide voice clustering, independent of Whisper decoding."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import time
from core import atomic_json, read_json, transcript


def cluster_voices(vectors, count=0, threshold=.35):
    import numpy as np
    from scipy.cluster.vq import kmeans2
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import laplacian, connected_components
    from scipy.sparse.linalg import eigsh
    if len(vectors) < 2:
        return [0]*len(vectors)
    matrix = np.asarray(vectors)
    if len(matrix)>=20:
        # Nearest-neighbour spectral clustering is insensitive to the absolute
        # cosine scale of a particular embedding model. Eigengap estimates k.
        # Downsample only clustering references to bound quadratic memory.
        indices=np.linspace(0,len(matrix)-1,min(len(matrix),3000),dtype=int)
        references=matrix[indices]
        affinity=references@references.T
        np.fill_diagonal(affinity,0)
        neighbors=min(20,len(references)-1)
        ids=np.argpartition(affinity,-neighbors,axis=1)[:,-neighbors:]
        r=np.repeat(np.arange(len(references)),neighbors);c=ids.ravel()
        graph=csr_matrix((np.maximum(affinity[r,c],0), (r,c)),shape=affinity.shape)
        graph=graph.maximum(graph.T)
        components,component_labels=connected_components(graph)
        if not count and components>1:
            canonical={}
            if len(references)==len(matrix):
                return [canonical.setdefault(int(x),len(canonical)) for x in component_labels]
        eigenvalues,eigenvectors=eigsh(laplacian(graph,normed=True),
            k=min(max(9,count+1),len(references)-1),which='SM',v0=np.ones(len(references)))
        order=np.argsort(eigenvalues);eigenvalues=eigenvalues[order];eigenvectors=eigenvectors[:,order]
        if not count:count=int(np.argmax(np.diff(eigenvalues[:9])))+1
        features=eigenvectors[:,1:count] if count>1 else np.zeros((len(references),1))
    else:
        references=matrix;indices=np.arange(len(matrix));features=matrix
        if not count:
            from scipy.cluster.hierarchy import linkage,fcluster
            labels=fcluster(linkage(matrix,method='average',metric='cosine'),threshold,criterion='distance')
            canonical={}
            return [canonical.setdefault(int(x),len(canonical)) for x in labels]
    if count>1:
        candidates=[]
        for seed in range(5):
            centers, labels=kmeans2(features,min(count,len(features)),minit='++',iter=50,seed=seed)
            candidates.append((float(np.sum((features-centers[labels])**2)),labels))
        labels=min(candidates,key=lambda item:item[0])[1]
    else:
        labels=np.zeros(len(references),dtype=int)
    if len(references)!=len(matrix):
        centers=np.array([references[labels==i].mean(axis=0) for i in range(count)])
        centers/=np.maximum(np.linalg.norm(centers,axis=1,keepdims=True),1e-8)
        labels=np.argmax(matrix@centers.T,axis=1)
    canonical = {}
    return [canonical.setdefault(int(x), len(canonical)) for x in labels]


def rediarize(folder, config, output=None):
    """Read original WAVs; output may be a separate review folder."""
    import numpy as np
    import soundfile as sf
    import sherpa_onnx as so
    from scipy.signal import resample_poly
    from math import gcd
    folder = Path(folder); output = Path(output or folder)
    output.mkdir(parents=True, exist_ok=True)
    root = Path(config['model_root']); started = time.perf_counter()
    emb = so.SpeakerEmbeddingExtractorConfig(model=str(root/'speaker-eres2net.onnx'), num_threads=2)
    extractor = so.SpeakerEmbeddingExtractor(emb)
    seg = so.OfflineSpeakerSegmentationModelConfig(
        pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(root/'segmentation-fp32.onnx')), num_threads=2)
    model = so.OfflineSpeakerDiarization(so.OfflineSpeakerDiarizationConfig(
        segmentation=seg, embedding=emb,
        clustering=so.FastClusteringConfig(num_clusters=-1, threshold=.5),
        min_duration_on=.2, min_duration_off=.2))
    turns=[]; vectors=[]
    jobs=sorted([read_json(p,{}) for p in (folder/'audio').glob('*.json')], key=lambda j:j.get('offset',0))
    # Bounded audio memory. All embeddings, not just drifting online centroids,
    # participate in the final identity assignment.
    for n, job in enumerate(jobs):
        if 'file' not in job:continue
        audio,sr=sf.read(folder/'audio'/job['file'],dtype='float32')
        if audio.ndim>1:audio=audio.mean(axis=1)
        g=gcd(sr,16000); audio=resample_poly(audio,16000//g,sr//g)
        local=model.process(audio).sort_by_start_time()
        windows=[]
        for turn in local:
            # A segmentation model can miss a turn boundary. Never pool an
            # entire 12-second conversation into a single speaker embedding.
            start=turn.start
            while start<turn.end-.75:
                end=min(start+2.,turn.end)
                windows.append(SimpleNamespace(start=start,end=end))
                start+=1.5
        for turn in windows:
            # Short utterances get labels by overlap only; do not build identity
            # from a tiny/noisy embedding.
            if turn.end-turn.start<.75:continue
            voice=audio[int(turn.start*16000):int(turn.end*16000)]
            stream=extractor.create_stream();stream.accept_waveform(16000,voice);stream.input_finished()
            if not extractor.is_ready(stream):continue
            vec=np.asarray(extractor.compute(stream),dtype=np.float32)
            norm=np.linalg.norm(vec)
            if not np.isfinite(norm) or norm<1e-8:continue
            vectors.append(vec/norm)
            turns.append(dict(start=job['offset']+turn.start,end=job['offset']+turn.end,
                              source=job['source']))
        if n%25==0:
            from engine import event
            event(output,'diarizing',f'전체 화자 재검토 중 · {n+1}/{len(jobs)}')
    if not turns:raise RuntimeError('화자 재검토에 사용할 음성을 찾지 못했습니다. 원음을 보존합니다.')
    # Embeddings are transient voice data, kept only in memory in normal runs.
    if config.get('diagnostic_features'):
        np.savez_compressed(output/'speaker_features.npz',vectors=np.asarray(vectors))
    labels=cluster_voices(vectors, int(config.get('speaker_count',0)),
                          1-max(.1,float(config.get('speaker_threshold',.65))-.4))
    for turn,label in zip(turns,labels):turn['speaker']=f'참석자{label+1}'
    rows=transcript(folder); result=[]
    aligned=[]
    for row in rows:
        if row.get('words'):
            aligned.extend(dict(start=w['start'],end=w['end'],text=w['text'],
                                source=row.get('source','mic'),words=[w]) for w in row['words'])
        else:aligned.append(row)
    for row in aligned:
        overlaps=[t for t in turns if t['source']==row.get('source','mic') and t['end']>row['start'] and t['start']<row['end']]
        totals={}
        for t in overlaps:
            totals[t['speaker']]=totals.get(t['speaker'],0)+min(row['end'],t['end'])-max(row['start'],t['start'])
        # Text rows may already span several speakers: do not invent a word split
        # without saved word timestamps. Flag ambiguous rows for review.
        ranked=sorted(totals.items(),key=lambda x:x[1],reverse=True)
        speaker=ranked[0][0] if ranked else '화자 미확인'
        if len(ranked)>1 and ranked[1][1] > max(.5, sum(totals.values())*.25):
            speaker='화자 전환 확인 필요'
        updated=dict(row,speaker=speaker)
        if (updated.get('words') and result and result[-1].get('words')
                and result[-1]['speaker']==speaker and result[-1].get('source')==updated.get('source')
                and updated['start']-result[-1]['end']<1.2):
            result[-1]['end']=updated['end'];result[-1]['text']+=updated['text']
            result[-1]['words'].extend(updated['words'])
        else:result.append(updated)
    for row in result:row['text']=row['text'].strip()
    atomic_json(output/'diarization.json',dict(version=1,seconds=time.perf_counter()-started,
        speakers=len(set(labels)),expected_speakers=config.get('speaker_count',0),turns=turns,
        review_rows=sum(not r['speaker'].startswith('참석자') for r in result)))
    temp=output/'transcript.diarizing.tmp'
    with temp.open('w',encoding='utf-8') as f:
        for row in result:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        f.flush();os.fsync(f.fileno())
    os.replace(temp,output/'transcript.jsonl')
    return result
