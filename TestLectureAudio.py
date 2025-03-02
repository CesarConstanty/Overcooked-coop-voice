import wave
import pyaudio
sound_file_path="static/sounds/pot.wav"
sound = wave.open(sound_file_path, mode = 'rb')
sound

def play_audio_file(sound_file_path):
    chunk = 1024
    wf = wave.open(sound_file_path, 'rb')
    p = pyaudio.PyAudio()
    p.get_default_output_device_info()
    stream = p.open(
        format = p.get_format_from_width(wf.getsampwidth()),
        channels = wf.getnchannels(),
        rate = wf.getframerate(),
        output = True
    )
    data = wf.readframes(chunk)
    while data:
        stream.write(data)
        data = wf.readframes(chunk)
    stream.close()
    p.terminate()
    return

play_audio_file(sound_file_path)

p = pyaudio.PyAudio()
p.get_default_output_device_info()

p = pyaudio.PyAudio()
device_count = p.get_device_count()

if device_count == 0:
    print("Aucun périphérique audio trouvé.")
else:
    for i in range(device_count):
        dev_info = p.get_device_info_by_index(i)
        print(f"ID: {i}, Nom: {dev_info['name']}, Type: {dev_info['maxOutputChannels']} canaux")

p.terminate()