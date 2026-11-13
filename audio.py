"""Preloaded, non-blocking damage feedback for the pygame client."""

from pathlib import Path

import pygame


IMPACTS_PATH = Path(__file__).resolve().parent / "assets" / "sounds" / "impacts"


class ImpactAudio:
    def __init__(self, path: Path = IMPACTS_PATH):
        self.error = ""
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        if pygame.mixer.get_init() is None:
            self.error = "Audio indisponivel: nao foi possivel inicializar o dispositivo de som."
            return
        try:
            sounds = {
                name: pygame.mixer.Sound(str(path / f"{name}.wav"))
                for name in ("light", "medium", "heavy")
            }
        except (OSError, pygame.error) as error:
            self.error = f"Audio indisponivel: erro ao carregar impactos: {error}"
            return
        pygame.mixer.set_num_channels(max(16, pygame.mixer.get_num_channels()))
        for sound in sounds.values():
            sound.set_volume(0.45)
        self.sounds = sounds

    def play_damage(self, amount: int) -> None:
        if amount <= 0 or not self.sounds:
            return
        name = "light" if amount <= 2 else "medium" if amount <= 4 else "heavy"
        # Concurrent hits overlap; force playback rather than silently dropping a hit.
        channel = pygame.mixer.find_channel(force=True)
        channel.play(self.sounds[name])
