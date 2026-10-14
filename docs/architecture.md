# 로컬 회의록 설계

## 확인한 PC
- AORUS Master 16 6XJ, AMD Ryzen 9 9955HX3D: 16코어 / 32스레드
- RAM 33,480,339,456 bytes (약 31.2 GiB), RTX 5070 Ti Laptop 12GB
- 기존 35B GGUF는 약 22GB로 업무 병행 시 메모리 부담이 커 전용 9B 모델을 사용한다.

## 선택한 구성
- 한국어: seastar105/whisper-medium-komixv2 → CTranslate2 INT8/FP16 변환.
- 한·영 혼용: Whisper large-v3 → CTranslate2 INT8/FP16 추론.
- 화자 분리: pyannote segmentation 3.0 INT8 ONNX + WeSpeaker ResNet34 ONNX, CPU 2스레드. 구간별 분리 결과를 음성 임베딩으로 연결한다.
- 회의록: Qwen3.5-9B Q4_K_M + llama.cpp, 종료 후에만 실행. STT 프로세스를 먼저 종료해 GPU 메모리를 회수한다.
- GUI: PySide6, 원음 디스크 저장, 별도 분석 프로세스, DOCX 내보내기.
- 기본 CPU 4스레드 / 낮은 우선순위. GPU 여유와 RAM 상태를 확인한다.
- 실행 중 인터넷 모델 다운로드 없음. 모델 준비는 개발/설치 단계에서만 수행한다.

## 평가 근거와 한계
2026-10-15 조회. 한국어 벤치마크의 평균 CER은 komixv2 7.05%, large-v3 7.83%, turbo 9.36%, Qwen3-ASR-1.7B 9.78%였다. 평가자는 30초 이하 발화의 결과이며 장시간 성능으로 일반화하지 말라고 명시한다. 실제 회의에서 최고라는 의미는 아니다. Raon 9B는 해당 평가에서 더 낮은 CER이지만 서버 자원 요구와 실행 속도가 이 PC의 동시 작업 목적에 불리하다.

## 참고 자료
- https://github.com/seastar105/oss-asr-korean-benchmark (원 평가 실험)
- https://huggingface.co/seastar105/whisper-medium-komixv2
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/QwenLM/Qwen3-ASR
- https://huggingface.co/unsloth/Qwen3.5-9B-GGUF
- https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html
- https://github.com/Zackriya-Solutions/meetily : 녹음과 실시간 발언을 중심으로 한 화면 구성
- https://github.com/imnotwallace/LocalScribe : Windows 로컬 우선, 마이크/시스템 오디오 캡처
- https://github.com/Knuckles92/OpenWhisper : 음성 엔진 선택과 로컬 기록 관리

참고 프로젝트의 소스를 복사하지 않고 새로 구현한다. 발언이 없는 참석자는 음성으로 셀 수 없으며 겹침/짧은 발화의 화자 판정은 추정이다.
