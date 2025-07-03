import numpy as np
import simpleaudio as sa
import tkinter as tk
from tkinter import messagebox, filedialog

# Frequencies for 4th octave notes, sharps (#) and flats (b) included
NOTE_FREQS = {
    'C':261.63, 'C#':277.18, 'Db':277.18,
    'D':293.66, 'D#':311.13, 'Eb':311.13,
    'E':329.63,
    'F':349.23, 'F#':369.99, 'Gb':369.99,
    'G':392.00, 'G#':415.30, 'Ab':415.30,
    'A':440.00, 'A#':466.16, 'Bb':466.16,
    'B':493.88,
    'R':0.0  # Rest
}

# Duration abbreviations in beats (BPM = 60)
TEMPO_BASE = {
    'w': 4.0,  # whole
    'h': 2.0,  # half
    'q': 1.0,  # quarter
    'dq': 1.5, # dotted quarter
    'e': 0.5,  # eighth
    's': 0.25, # sixteenth
    't': 1/3,  # triplet
}

def adjust_tempo(bpm):
    factor = 60 / bpm
    return {k: v * factor for k, v in TEMPO_BASE.items()}

# Default BPM
BPM = 120
TEMPO = adjust_tempo(BPM)

# Audio sample rate
FS = 44100

def sine_wave(frequency, duration, volume=0.5, fade_ms=20):
    if frequency == 0:
        return np.zeros(int(FS * duration), dtype=np.int16)
    t = np.linspace(0, duration, int(FS*duration), False)
    wave_data = np.sin(frequency * t * 2 * np.pi) * volume
    audio = (wave_data * 32767).astype(np.int16)

    # Apply fade in/out in samples
    fade_samples = int(fade_ms * FS / 1000)
    fade_in = np.linspace(0., 1., fade_samples)
    fade_out = np.linspace(1., 0., fade_samples)
    audio[:fade_samples] = (audio[:fade_samples].astype(np.float32) * fade_in).astype(np.int16)
    audio[-fade_samples:] = (audio[-fade_samples:].astype(np.float32) * fade_out).astype(np.int16)

    return audio

def mix_audio_segments(segments):
    """ Mix multiple 1D numpy arrays by summing and clipping """
    if not segments:
        return np.array([], dtype=np.int16)
    max_len = max(len(s) for s in segments)
    mix = np.zeros(max_len, dtype=np.int32)
    for seg in segments:
        mix[:len(seg)] += seg.astype(np.int32)
    # Clip to int16 range
    mix = np.clip(mix, -32768, 32767)
    return mix.astype(np.int16)

def play_audio_np(audio_np):
    play_obj = sa.play_buffer(audio_np, 1, 2, FS)
    play_obj.wait_done()

def parse_note_token(token):
    token = token.strip()
    duration = None
    # Find longest matching duration key suffix
    for d in sorted(TEMPO_BASE.keys(), key=lambda x: -len(x)):
        if token.endswith(d):
            duration = d
            notes_part = token[:-len(d)]
            break
    if duration is None:
        duration = 'q'  # default quarter
        notes_part = token
    # Parse chord if any
    if notes_part.startswith('[') and notes_part.endswith(']'):
        notes_str = notes_part[1:-1]
        notes = []
        i = 0
        while i < len(notes_str):
            if i+1 < len(notes_str) and notes_str[i+1] in ['#','b']:
                notes.append(notes_str[i:i+2])
                i += 2
            else:
                notes.append(notes_str[i])
                i += 1
    else:
        if len(notes_part) == 0:
            notes = ['R']  # rest if empty
        elif len(notes_part) > 1 and notes_part[1] in ['#','b']:
            notes = [notes_part[:2]]
        else:
            notes = [notes_part]
    return notes, duration

def generate_note_audio(note, duration_sec, volume=0.5):
    freq = NOTE_FREQS.get(note, None)
    if freq is None:
        raise ValueError(f"Unknown note: {note}")
    audio_np = sine_wave(freq, duration_sec, volume)
    return audio_np

def play_song(tokens, bpm=120, volume=0.5):
    global TEMPO
    TEMPO = adjust_tempo(bpm)
    segments = []
    for token in tokens:
        notes, dur_key = parse_note_token(token)
        duration_sec = TEMPO.get(dur_key)
        if duration_sec is None:
            print(f"Unknown duration '{dur_key}' in token '{token}', skipping.")
            continue
        chord_segments = []
        for note in notes:
            seg = generate_note_audio(note, duration_sec, volume)
            chord_segments.append(seg)
        combined = mix_audio_segments(chord_segments)
        segments.append(combined)
    if not segments:
        return np.array([], dtype=np.int16)
    song = np.concatenate(segments)
    play_audio_np(song)
    return song

def export_song(audio_np):
    root = tk.Tk()
    root.withdraw()
    filetypes = [("WAV files", "*.wav")]
    filename = filedialog.asksaveasfilename(title="Save audio file", defaultextension=".wav", filetypes=filetypes)
    if not filename:
        return False
    import wave
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(FS)
        wf.writeframes(audio_np.tobytes())
    messagebox.showinfo("Export Complete", f"File saved as: {filename}")
    return True

class MusicPlayerGUI:
    def __init__(self, master):
        self.master = master
        master.title("Python Music Player")

        self.bpm = BPM
        self.volume = 0.5

        tk.Label(master, text="Enter notes (e.g. Cq Dq [CEG]h Ebq):").grid(row=0, column=0, columnspan=3, sticky='w')
        self.text_notes = tk.Text(master, height=5, width=50)
        self.text_notes.grid(row=1, column=0, columnspan=3, padx=5, pady=5)

        tk.Label(master, text="BPM:").grid(row=2, column=0)
        self.bpm_entry = tk.Entry(master, width=5)
        self.bpm_entry.insert(0, str(self.bpm))
        self.bpm_entry.grid(row=2, column=1)

        tk.Label(master, text="Volume (0-1):").grid(row=2, column=2)
        self.vol_entry = tk.Entry(master, width=5)
        self.vol_entry.insert(0, str(self.volume))
        self.vol_entry.grid(row=2, column=3)

        self.play_button = tk.Button(master, text="Play", command=self.play_song)
        self.play_button.grid(row=3, column=0, pady=10)

        self.export_button = tk.Button(master, text="Export WAV", command=self.export_wav)
        self.export_button.grid(row=3, column=1)

    def play_song(self):
        notes_str = self.text_notes.get("1.0", "end").strip()
        tokens = notes_str.split()
        try:
            bpm = float(self.bpm_entry.get())
            volume = float(self.vol_entry.get())
            if not (0 <= volume <= 1):
                raise ValueError("Volume must be between 0 and 1")
            self.bpm = bpm
            self.volume = volume
            play_song(tokens, bpm, volume)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_wav(self):
        notes_str = self.text_notes.get("1.0", "end").strip()
        tokens = notes_str.split()
        try:
            bpm = float(self.bpm_entry.get())
            volume = float(self.vol_entry.get())
            audio_np = play_song(tokens, bpm, volume)
            export_song(audio_np)
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = MusicPlayerGUI(root)
    root.mainloop()
