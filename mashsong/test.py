import numpy as np
from pathlib import Path
import librosa
import librosa.display
import matplotlib.pyplot as plt

path = Path(__file__).parent.parent / "data/music/src"

fps=100
sr=44100
n_fft=2048
hop_length = int(librosa.time_to_samples(1./fps, sr=sr))

y, sr = librosa.load(str(path/"DieForYou.wav"), duration=15, sr=sr)

chroma = librosa.feature.chroma_stft(y, sr=sr, n_fft=n_fft, hop_length=hop_length)
flux = librosa.onset.onset_strength(S=chroma, sr=sr, hop_length=512)

frame_time = librosa.frames_to_time(np.arange(len(flux)), sr=sr, hop_length=hop_length)

fig, ax = plt.subplots(nrows=2, sharex=True, figsize=(14,6))

img = librosa.display.specshow(chroma, y_axis='chroma',x_axis='time',ax=ax[0], hop_length=hop_length)
ax[0].set_title('Chromagram', fontsize=15)

ax[1].plot(frame_time, flux, label='Spectral Flux')
ax[1].set_title('Spectral Flux', fontsize=15)
ax[1].set(xlabel='Time')
ax[1].set(xlim=[0, len(y)/sr]);
ax[0].label_outer()
plt.show()