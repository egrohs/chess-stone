"""Generate original, deterministic impact WAVs using only the standard library."""

import math
import random
import struct
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "assets" / "sounds" / "impacts"
SAMPLE_RATE = 44100
PROFILES = {
    "light": (0.12, 180, 0.30),
    "medium": (0.18, 115, 0.40),
    "heavy": (0.26, 70, 0.50),
}


def generate(destination: Path = ROOT) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for index, (name, (duration, pitch, noise_mix)) in enumerate(PROFILES.items()):
        rng = random.Random(4200 + index)
        frames = bytearray()
        phase = 0.0
        filtered_noise = 0.0
        count = round(duration * SAMPLE_RATE)
        for sample in range(count):
            time = sample / SAMPLE_RATE
            phase += 2 * math.pi * pitch * (1 + 2.5 * math.exp(-time * 65)) / SAMPLE_RATE
            noise = rng.uniform(-1, 1)
            filtered_noise = 0.65 * filtered_noise + 0.35 * noise
            envelope = min(1.0, time / 0.001) * math.exp(-time * 8 / duration)
            tail = min(1.0, (count - sample - 1) / (SAMPLE_RATE * 0.005))
            tone = math.sin(phase) * (1 - noise_mix)
            crack = (noise * math.exp(-time * 100) + filtered_noise) * noise_mix
            value = round(20000 * (tone + crack) * envelope * tail)
            frames.extend(struct.pack("<h", max(-32768, min(32767, value))))
        with wave.open(str(destination / f"{name}.wav"), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(SAMPLE_RATE)
            stream.writeframes(frames)


if __name__ == "__main__":
    generate()
    print(f"Impactos gerados em {ROOT}")
