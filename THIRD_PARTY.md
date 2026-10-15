# 오픈소스·모델 안내

본 앱 소스의 라이선스는 저장소의 MIT LICENSE를 따른다. 함께 사용하는 라이브러리·모델에는 각각의 라이선스가 적용된다. 배포 전 각 원본의 현재 조건을 확인한다.

- PySide6 / Qt: LGPLv3/GPLv3 또는 상용 라이선스. 동적 DLL로 배포하며 설치 폴더에서 교체 가능. https://doc.qt.io/qtforpython-6/licenses.html
- faster-whisper: MIT. https://github.com/SYSTRAN/faster-whisper
- CTranslate2: MIT. https://github.com/OpenNMT/CTranslate2
- Kiwi / kiwipiepy 0.23.1: LGPLv3. 모델·패키지 파일은 `_internal/kiwipiepy_model`에 별도 배포되어 교체 가능. https://github.com/bab2min/kiwipiepy
- KoGrammar-base: MIT, KoBART 기반 국립국어원 맞춤법 교정 말뭉치 학습 모델. CTranslate2 INT8/FP16 변환. https://huggingface.co/theSOL1/kogrammar-base
- 3D-Speaker ERes2Net: Apache-2.0 원 프로젝트 및 ONNX 배포 조건. https://github.com/modelscope/3D-Speaker / https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models
- Whisper: MIT. https://github.com/openai/whisper
- 한국어 특화 가중치: https://huggingface.co/seastar105/whisper-medium-komixv2 (모델 카드 및 학습 데이터 이용 조건 참조)
- sherpa-onnx: Apache-2.0. https://github.com/k2-fsa/sherpa-onnx
- pyannote segmentation 3.0 / WeSpeaker ONNX: 원 모델·변환 배포의 조건 적용. https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models / https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models
- Qwen3.5-9B: Apache-2.0. https://huggingface.co/Qwen/Qwen3.5-9B
- GGUF 양자화 배포: https://huggingface.co/unsloth/Qwen3.5-9B-GGUF
- llama.cpp: MIT. https://github.com/ggml-org/llama.cpp
- NVIDIA CUDA/cuDNN/cuBLAS: NVIDIA 재배포 조건 적용. 시스템 드라이버는 설치된 드라이버 사용.
- python-docx: MIT. https://github.com/python-openxml/python-docx
- PyAudioWPatch: MIT. https://github.com/s0d3s/PyAudioWPatch

Meetily, LocalScribe, OpenWhisper는 UI/기능 설계 참고 자료이다. 해당 소스를 포함하지 않는다.
