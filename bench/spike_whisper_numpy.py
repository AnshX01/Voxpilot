import time
import wave
import numpy as np
import faster_whisper

print("Loading faster-whisper (tiny.en)...")
model = faster_whisper.WhisperModel("tiny.en", device="cpu", compute_type="int8")

def load_wav_numpy(path):
    with wave.open(path, "rb") as wf:
        data = wf.readframes(wf.getnframes())
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        return audio

def test_whisper(wav_path):
    audio = load_wav_numpy(wav_path)
    t_start = time.perf_counter()
    segments, info = model.transcribe(audio, beam_size=1)
    text = " ".join([s.text for s in list(segments)]).strip()
    t_end = time.perf_counter()
    print(f"Transcribed '{wav_path}': '{text}' in {(t_end - t_start)*1000:.2f} ms")

test_whisper("fixtures/audio/twenty_three.wav")
test_whisper("fixtures/audio/show_numbers.wav")
test_whisper("fixtures/audio/twelve.wav")
