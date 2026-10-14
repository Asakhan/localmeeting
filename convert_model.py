from pathlib import Path
import sys,os
root=Path(__file__).resolve().parent
os.environ['OMP_NUM_THREADS']='4'
sys.path.append(str(Path.home()/'Documents/tools/local_minutes/.venv/Lib/site-packages'))
import torch
torch.set_num_threads(4)
from ctranslate2.converters import TransformersConverter
from transformers import WhisperTokenizer
src=root/'models/komix-source'
tok=WhisperTokenizer.from_pretrained(str(src),local_files_only=True)
tok.save_pretrained(str(src))
TransformersConverter(str(src),copy_files=['tokenizer.json','preprocessor_config.json']).convert(str(root/'models/komix'),quantization='int8_float16',force=True)
print('CONVERTED',flush=True)
