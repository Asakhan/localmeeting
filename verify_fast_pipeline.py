"""Read-only meeting benchmark. All outputs go under test-output."""
import argparse
import time
from pathlib import Path
from core import transcript, atomic_json, read_json
from engine import runtime_setup
from fast_correction import correct_fast


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('meeting',type=Path)
    args=parser.parse_args()
    rows=transcript(args.meeting)
    runtime_setup(4)
    output=Path('test-output/fast-benchmark');output.mkdir(parents=True,exist_ok=True)
    metrics=[]
    for name, data in [('60-minute-equivalent',rows+[
            dict(r,start=r['start']+3335,end=r['end']+3335) for r in rows if r['start']<265]),('actual',rows)]:
        dest=output/name;dest.mkdir(exist_ok=True)
        start=time.perf_counter()
        result=correct_fast(dest,data,model_root=Path('models'))
        seconds=time.perf_counter()-start
        audit=read_json(dest/'transcript_corrections.json')
        metrics.append(dict(case=name,rows=len(data),chars=sum(len(r['text']) for r in data),
                            seconds=seconds,edits=len(audit['edits']),grammar=audit['grammar']))
        assert len(result)==len(data)
        assert audit['grammar']['complete'], 'Not all chunks were reviewed'
        assert seconds<60, f'{name}: {seconds:.2f}s exceeds target'
        print(metrics[-1],flush=True)
    atomic_json(output/'metrics.json',metrics)


if __name__=='__main__':main()
