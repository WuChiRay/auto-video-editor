"""Create a locally synthesized 120 BPM workout instrumental; no sampled audio."""
from pathlib import Path
import argparse
import wave
import numpy as np


def generate(path: Path, duration: float = 48, bpm: float = 120) -> None:
    sr = 48000
    beat = 60 / bpm
    n = round(duration * sr)
    out = np.zeros((n, 2), dtype=np.float64)
    rng = np.random.default_rng(120)

    def add(at, signal, level, pan=0):
        start = round(at * sr)
        size = min(len(signal), n-start)
        if size <= 0:
            return
        out[start:start+size, 0] += signal[:size] * level * (1-pan*.4)
        out[start:start+size, 1] += signal[:size] * level * (1+pan*.4)

    def tone(freq, length, decay):
        t = np.arange(round(length*sr))/sr
        return (np.sin(2*np.pi*freq*t) + .25*np.sin(4*np.pi*freq*t)) * np.minimum(t/.008, 1)*np.exp(-decay*t)

    roots = [45, 41, 48, 43]  # A minor, F, C, G
    beats = int(np.ceil(duration/beat))
    for b in range(beats):
        at = b*beat
        t = np.arange(round(.25*sr))/sr
        phase = 2*np.pi*(48*t + (125-48)*.028*(1-np.exp(-t/.028)))
        add(at, np.sin(phase)*np.exp(-18*t), .38)
        if b % 2 == 1:
            t = np.arange(round(.14*sr))/sr
            noise = rng.normal(0, 1, len(t))
            noise = noise-np.concatenate(([0], noise[:-1]))*.75
            add(at, noise*np.exp(-40*t), .065)
        for half in (0, .5):
            t = np.arange(round(.065*sr))/sr
            noise = rng.normal(0, 1, len(t))
            noise = noise-np.concatenate(([0], noise[:-1]))*.96
            add(at+half*beat, noise*np.exp(-75*t), .032, .3 if half else -.3)
        root = roots[(b//4) % 4]
        freq = 440*2**((root-69)/12)
        add(at, tone(freq, .38, 8), .17)
        for half in (0, .5):
            step = [12, 19, 24, 19, 15, 19, 24, 19][(b%4)*2+int(half*2)]
            note = root+step+12
            add(at+half*beat, tone(440*2**((note-69)/12), .32, 14), .05, (-1)**b*.5)
    fade = np.minimum(np.arange(n)/(sr*.4), 1)*np.minimum((n-1-np.arange(n))/(sr*1.2), 1)
    out *= fade[:, None]
    out = np.tanh(out*1.2)
    out *= .85/max(np.max(np.abs(out)), .001)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes((out*32767).astype('<i2').tobytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--duration', type=float, default=48)
    args = parser.parse_args()
    generate(args.output, args.duration)
