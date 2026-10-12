import os
import win32com.client

os.makedirs("fixtures/audio", exist_ok=True)

def generate_wav(text, filename, voice_index=1):
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    
    # Format: 16kHz 16-bit Mono (SAFT16kHz16BitMono = 22)
    stream.Format.Type = 22
    
    voice.Voice = voice.GetVoices().Item(voice_index)
    stream.Open(filename, 3, False) # 3 = SSFMCreateForWrite
    voice.AudioOutputStream = stream
    voice.Speak(text)
    stream.Close()
    print(f"Generated {filename}: '{text}'")

if __name__ == "__main__":
    generate_wav("twenty three", "fixtures/audio/twenty_three.wav", 1) # Zira (en-US)
    generate_wav("show numbers", "fixtures/audio/show_numbers.wav", 1)
    generate_wav("click forty two", "fixtures/audio/click_42.wav", 0) # Hazel (en-GB)
    generate_wav("show grid", "fixtures/audio/show_grid.wav", 1)
    generate_wav("twelve", "fixtures/audio/twelve.wav", 1)
