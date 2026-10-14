"""Desktop and worker entry point. Frozen executable launches its own workers."""
import sys, os

def main():
    if '--transcribe' in sys.argv:
        from engine import run_transcription
        return run_transcription(sys.argv[sys.argv.index('--transcribe')+1])
    if '--summarize' in sys.argv:
        from summarize import run_summary
        return run_summary(sys.argv[sys.argv.index('--summarize')+1])
    from gui import run_gui
    return run_gui()

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    try:sys.exit(main())
    except Exception:
        import traceback
        from core import DATA
        DATA.mkdir(parents=True,exist_ok=True)
        (DATA/'crash.log').write_text(traceback.format_exc(),encoding='utf-8')
        if not any(x in sys.argv for x in ['--transcribe','--summarize']):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,f'실행 오류가 발생했습니다.\n{DATA / "crash.log"}', '로컬 회의록',0x10)
        raise
