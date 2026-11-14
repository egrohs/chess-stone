"""Preloaded, non-blocking sound feedback for the pygame client."""

from pathlib import Path

import pygame


IMPACTS_PATH = Path(__file__).resolve().parent / "assets" / "sounds" / "impacts"
EVENT_SOUNDS = {
    "your_turn": "ALERT_YourTurn_0v2.ogg",
    "end_turn_down": "FX_EndTurn_Down.ogg",
    "end_turn_up": "FX_EndTurn_Up.ogg",
    "freeze": "FX_FreezeEvent_SpellImpact.ogg",
    "opening_deal": "FX_GameStart20_CardDealSingle.ogg",
    "shuffle": "FX_MulliganCoin09_DeckShuffle.ogg",
    "draw": "draw_card_and_add_to_hand_1.ogg",
    "mana_add": "mana_crystal_add.ogg",
    "mana_expend": "mana_crystal_expend.ogg",
    "mana_refresh": "mana_crystal_refresh.ogg",
    "victory": "victory_screen_start.ogg",
}


class ImpactAudio:
    def __init__(self, path: Path = IMPACTS_PATH):
        self.error = ""
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.event_sounds: dict[str, pygame.mixer.Sound] = {}
        if pygame.mixer.get_init() is None:
            self.error = "Audio indisponivel: nao foi possivel inicializar o dispositivo de som."
            return
        pygame.mixer.set_num_channels(max(16, pygame.mixer.get_num_channels()))
        errors = []
        for name in ("light", "medium", "heavy"):
            try:
                sound = pygame.mixer.Sound(str(path / f"{name}.wav"))
                sound.set_volume(0.45)
                self.sounds[name] = sound
            except (OSError, pygame.error) as error:
                errors.append(f"erro ao carregar impactos ({name}): {error}")
        for event, filename in EVENT_SOUNDS.items():
            try:
                sound = pygame.mixer.Sound(str(path.parent / filename))
                sound.set_volume(0.45)
                self.event_sounds[event] = sound
            except (OSError, pygame.error) as error:
                errors.append(f"{filename}: {error}")
        if errors:
            self.error = "Audio incompleto: erro ao carregar sons: " + "; ".join(errors)

    def play_event(self, event: str) -> None:
        sound = self.event_sounds.get(event)
        if sound is not None:
            channel = pygame.mixer.find_channel(force=True)
            channel.play(sound)

    def play_damage(self, amount: int) -> None:
        if amount <= 0:
            return
        name = "light" if amount <= 2 else "medium" if amount <= 4 else "heavy"
        sound = self.sounds.get(name)
        if sound is None:
            return
        # Concurrent hits overlap; force playback rather than silently dropping a hit.
        channel = pygame.mixer.find_channel(force=True)
        channel.play(sound)
