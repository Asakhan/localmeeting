# 아사검의 회의록 · Khan's Minutes

Windows에서 인터넷 없이 녹음, 한국어/한영 음성 인식, 화자 분리, 회의록 작성 및 Word 저장을 수행하는 데스크톱 프로그램입니다. 메뉴는 **회의녹음 / 회의록 보기 / 설정** 세 가지입니다.

## 실행

`dist\LocalMeeting\KhansMinutes.exe`를 실행합니다. EXE가 들어 있는 폴더 전체가 실행 패키지입니다. Python 설치는 필요하지 않습니다. 모델과 DLL이 함께 있어야 하므로 EXE 파일 하나만 다른 곳으로 옮기지 마세요.

기본 저장 폴더: `C:\Users\문근영\Documents\회의록` (다른 사용자 계정에서는 해당 계정의 `Documents\회의록`).

1. **설정**에서 마이크와 회의 언어를 선택합니다. 대면 한국어 회의가 기본값입니다. 온라인 회의는 컴퓨터 음성도 녹음을 켜고, 헤드폰 사용을 권장합니다.
2. **회의녹음 → 회의 녹음 시작**을 누릅니다. 약 12초 단위의 시간·화자별 발언이 표시됩니다. 첫 모델 준비 중에도 녹음은 디스크에 저장됩니다.
3. **회의 종료**를 누르면 남은 발언을 전사하고 음성 모델을 종료한 뒤 회의록을 작성합니다.
4. **회의록 보기**에서 내용을 확인하고 참석자 이름을 입력한 뒤 **이름 일괄 적용**을 누릅니다. Word와 전체 전사 TXT에 함께 반영됩니다.

각 회의 폴더에 `회의록.docx`, `전체전사.txt`, 이름 수정/복구를 위한 JSON 메타데이터가 저장됩니다. Word를 열어 둬 덮어쓸 수 없으면 수정본을 별도 파일로 저장하고 앱의 Word 열기가 최신 수정본을 가리킵니다.

회의록 항목: 회의명, 시작·종료 일시, 참석자, 안건, 주요 논의사항, 제안 사항, 결정 사항, 미결 사항, 실행 과제(담당자·기한·할 일), 후속 일정. 부록으로 전체 발언도 포함합니다. 발언에 없던 결정·기한은 만들지 않도록 지시하며, 확인되지 않은 항목은 표시합니다.

## 오디오 자동 삭제

모든 음성 조각의 전사 처리와 Word/TXT 파일 저장을 확인한 뒤 **그 회의의 원음과 임시 음성 조각을 자동 삭제**합니다. 완료 후에는 음성을 다시 들을 수 없습니다.

녹음 장치 오류, 전사 실패, 모델 오류, 디스크 부족, 복구 중인 녹음, 인식된 발언이 없는 녹음은 자동 삭제하지 않습니다. **회의록 보기 → 다시 처리**로 재시도할 수 있습니다. 비정상 종료에서 복구된 녹음은 누락 확인이 필요하므로 자동 삭제하지 않습니다. 앱 오류가 있어도 원음이 남아 있는 동안 재처리가 가능합니다.

## 모델·자원 사용

- 한국어: `Whisper large-v3` INT8. 기존 한국어 특화 medium 모델의 문장 덧붙임 현상을 줄이기 위해 교체했습니다. 무음·단어 시간 정렬을 검사하며 신뢰도가 낮은 단어는 `[청취 불명확]`으로 표시합니다.
- 한영 혼용: `Whisper large-v3`, CTranslate2 INT8/FP16 추론. 번역하지 않고 발언 언어대로 기록.
- 화자: pyannote segmentation 3.0 INT8 ONNX + WeSpeaker 임베딩. CPU 2스레드.
- 회의록: `Qwen3.5-9B Q4_K_M`, llama.cpp. STT 종료 후에만 시작하고 완료 시 종료.
- 기본 CPU 추론 4스레드, 낮은 프로세스 우선순위. GPU 여유 부족 시 CPU로 전환. RAM 여유가 부족하면 분석을 중단하고 녹음을 보존합니다.
- CPU 대체 경로는 느려 실시간 전사가 밀릴 수 있습니다. 녹음은 별도로 계속되고 종료 후 남은 구간을 처리합니다. GPU를 사용하는 기본 경로가 권장됩니다.
- 모델 로딩 이후에도 자원 사용량은 회의 길이/동시 프로그램에 따라 달라집니다. 수치는 [실측 검증 기록](docs/verification.md)을 참조하세요.
- 현재 확인된 PC: Ryzen 9 9955HX3D 16코어/32스레드, RAM 32GB, RTX 5070 Ti Laptop VRAM 12GB.

모델과 라이브러리는 최초 개발/설치 때 내려받습니다. **앱 실행 중 외부 API나 인터넷 다운로드를 사용하지 않습니다.** 회의록 모델은 임의 포트의 `127.0.0.1`에 임시 인증키로 실행하고 프록시를 사용하지 않습니다. 다른 로컬 AI 프로그램은 강제 종료하지 않습니다.

화자 수는 **말한 사람의 추정 인원**입니다. 말하지 않은 참석자, 동일한 목소리, 잡음, 겹침 발화는 정확히 구분하기 어렵습니다. 이름 자체는 음성으로 추측하지 않습니다. 실제 다인 회의의 정확도와 장시간 안정성은 사용 환경에서 추가 확인이 필요합니다. 공개 벤치마크만으로 모든 한국어 회의에서 최고 성능을 보장할 수는 없습니다.

## 개발·재현

Python 3.12 x64 및 NVIDIA 드라이버가 설치된 Windows 환경 기준입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe download_models.py
```

한국어 가중치 변환에는 **별도 개발 환경의 PyTorch/transformers**가 필요합니다. 이 PC에서는 기존 ComfyUI Python을 재사용합니다. 실행 EXE에는 PyTorch를 포함하지 않습니다.

```powershell
& 'C:\AI\ComfyUI_windows_portable\python_embeded\python.exe' .\convert_model.py
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build.py
```

빌드는 이 PC에 있는 `C:\AI\llama`에서 `llama-server.exe`와 DLL을 패키지로 복사합니다. 다른 PC에서 빌드할 때는 해당 경로에 CUDA 지원 llama.cpp Windows 배포를 준비하거나 `build.py`의 경로를 수정하세요. 이 PC의 정확한 설치 버전은 `requirements-lock.txt`에 기록했습니다.

통합 검사(공개 샘플 사용, 모델은 순차 실행):

```powershell
.\.venv\Scripts\python.exe verify_stt.py
.\.venv\Scripts\python.exe verify_performance.py
.\.venv\Scripts\python.exe verify_mixed.py
.\.venv\Scripts\python.exe verify_summary.py
.\.venv\Scripts\python.exe verify_gui.py
.\.venv\Scripts\python.exe verify_exe.py
```

`verify_stt.py`만 공개 테스트 음성을 다운로드합니다. 나머지 검증은 내려받은 파일을 재사용합니다. 테스트 산출물은 `test-output`에만 저장합니다. 실제 회의 폴더를 테스트에 사용하지 않습니다.

소스 구성: `capture.py`(녹음), `engine.py`(전사·화자), `summarize.py`(로컬 LLM), `core.py`(저장·DOCX/TXT), `gui.py`(화면), `app.py`(진입점), `winjob.py`(자식 프로세스 정리).

모델, 가상환경, EXE, 녹음, 회의록, 테스트 산출물은 Git에 올리지 않습니다. [설계·선정 근거](docs/architecture.md), [외부 구성 요소](THIRD_PARTY.md).
