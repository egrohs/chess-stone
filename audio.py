"""Preloaded, non-blocking sound feedback for the pygame client."""

from pathlib import Path
import sys

import pygame


IMPACTS_PATH = Path(__file__).resolve().parent / "assets" / "sounds" / "impacts"
MUSIC_PATH = IMPACTS_PATH.parent / "music"
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


class BackgroundMusic:
    def __init__(self, path: Path = MUSIC_PATH):
        self.path = path
        self.mode: str | None = None
        self.tracks: list[Path] = []
        self.index = 0
        self.error = ""

    def update(self, in_match: bool) -> None:
        mode = "match" if in_match else "menu"
        if mode != self.mode:
            self.mode = mode
            self.tracks = []
            self.index = 0
            self.error = ""
            if pygame.mixer.get_init() is None:
                self._report("dispositivo de audio indisponivel")
                return
            pygame.mixer.music.stop()
            try:
                files = sorted(
                    (file for file in self.path.iterdir()
                     if file.is_file() and file.suffix.lower() in {".mp3", ".ogg", ".wav"}),
                    key=lambda file: file.name.casefold(),
                )
                menu = [file for file in files if file.name.startswith("01.")]
                if len(menu) != 1:
                    raise ValueError("esperada uma unica faixa de menu iniciada por '01.'")
                self.tracks = [file for file in files if file != menu[0]] if in_match else menu
                if not self.tracks:
                    raise ValueError("nenhuma faixa de partida encontrada")
                self._play()
            except (OSError, ValueError, pygame.error) as error:
                self._report(str(error))
        elif self.tracks and not self.error and not pygame.mixer.music.get_busy():
            self.index = (self.index + 1) % len(self.tracks)
            try:
                self._play()
            except (OSError, pygame.error) as error:
                self._report(str(error))

    def _play(self) -> None:
        pygame.mixer.music.load(str(self.tracks[self.index]))
        pygame.mixer.music.set_volume(0.25)
        pygame.mixer.music.play(loops=-1 if self.mode == "menu" else 0)

    def _report(self, message: str) -> None:
        self.error = f"Musica indisponivel: {message}"
        print(self.error, file=sys.stderr)

    def stop(self) -> None:
        if pygame.mixer.get_init() is not None:
            pygame.mixer.music.stop()


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
