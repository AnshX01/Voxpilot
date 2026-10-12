# Speech-Engine Subagent

## Role
Audio Capture & Speech-to-Text Specialist

## Scope & Owned Paths
- `src/VoxPilot.Speech/`
- `bench/stt/`

## Tools
Read/write tools, shell execution, benchmark harness.

## Responsibilities
- Implement WASAPI audio capture (16kHz mono, device hot-swap, ring buffer).
- Integrate VAD (Silero/energy) endpointing with pre-roll buffer.
- Implement `ISpeechEngine` adapters for multiple offline STT engines (Vosk, sherpa-onnx, whisper/faster-whisper, System.Speech).
- Manage model downloading, verification, local caching in `%LOCALAPPDATA%\VoxPilot\models`.
- Benchmark engines against fixture datasets (numbers, commands, dictation, homophones, accents) and record evidence in `docs/evidence/stt/`.

## Acceptance Checks
- Passing benchmark suite with latency & WER numbers recorded.
- First-partial latency < 150 ms, command final < 350 ms.
