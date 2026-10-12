import time
import faster_whisper

print("Loading faster-whisper (tiny.en)...")
t0 = time.perf_counter()
model = faster_whisper.WhisperModel("tiny.en", device="cpu", compute_type="int8")
t1 = time.perf_counter()
print(f"Loaded in {(t1-t0)*1000:.2f} ms")

def test_whisper(wav_path):
    t_start = time.perf_counter()
    segments, info = model.transcribe(wav_path, beam_size=1)
    text = " ".join([s.text for s in segments]).strip()
    t_end = time.perf_counter()
    print(f"Transcribed '{wav_path}': '{text}' in {(t_end - t_start)*1000:.2f} ms")

test_whisper("fixtures/audio/twenty_three.wav")
test_whisper("fixtures/audio/show_numbers.wav")
