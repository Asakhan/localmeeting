"""Build-time only: download the MIT KoGrammar checkpoint and convert to CT2."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
sys.path.append(str(root/'.venv/Lib/site-packages'))
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer
from ctranslate2.converters import TransformersConverter
source=root/'models/kogrammar-source'
snapshot_download('theSOL1/kogrammar-base',local_dir=source,
                  allow_patterns=['*.json','*.safetensors','README.md'])
tokenizer=AutoTokenizer.from_pretrained(str(source))
tokenizer.save_pretrained(str(source))
TransformersConverter(str(source),copy_files=['tokenizer.json','README.md']).convert(
    str(root/'models/kogrammar'),quantization='int8_float16',force=True)
print('READY',flush=True)
