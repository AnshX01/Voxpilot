import json
import os
import time
import wave
import vosk

model_path = "models/vosk-model-small-en-us-0.15"
print(f"Loading Vosk model from {model_path}...")
t_load_0 = time.perf_counter()
model = vosk.Model(model_path)
t_load_1 = time.perf_counter()
print(f"Model loaded in {(t_load_1 - t_load_0)*1000:.2f} ms")

def benchmark_wav(wav_path, grammar=None):
    wf = wave.open(wav_path, "rb")
    if grammar:
        rec = vosk.KaldiRecognizer(model, wf.getframerate(), json.dumps(grammar))
    else:
        rec = vosk.KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    chunk_size = 1600 # 100ms at 16kHz
    first_partial_time = None
    partials = []
    
    t_start = time.perf_counter()
    while True:
        data = wf.readframes(chunk_size)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            if res.get("text"):
                partials.append(res["text"])
        else:
            partial_res = json.loads(rec.PartialResult())
            if partial_res.get("partial") and first_partial_time is None:
                first_partial_time = time.perf_counter() - t_start
                partials.append(partial_res["partial"])
    
    final_res = json.loads(rec.FinalResult())
    t_end = time.perf_counter()
    total_time = (t_end - t_start) * 1000
    recognized_text = final_res.get("text", "")
    
    print(f"\n--- Benchmark: {os.path.basename(wav_path)} ---")
    print(f"Final Text: '{recognized_text}'")
    print(f"First Partial Latency: {(first_partial_time or 0)*1000:.2f} ms")
    print(f"Total Processing Time: {total_time:.2f} ms")
    print(f"Audio Duration: {wf.getnframes() / wf.getframerate() * 1000:.2f} ms")
    print(f"Real-Time Factor (RTF): {total_time / (wf.getnframes() / wf.getframerate() * 1000):.3f}")
    return recognized_text, first_partial_time, total_time

if __name__ == "__main__":
    benchmark_wav("fixtures/audio/twenty_three.wav")
    benchmark_wav("fixtures/audio/show_numbers.wav")
    benchmark_wav("fixtures/audio/click_42.wav")
    benchmark_wav("fixtures/audio/show_grid.wav")
    benchmark_wav("fixtures/audio/twelve.wav")
