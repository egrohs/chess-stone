import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

from audio import IMPACTS_PATH, ImpactAudio
from game_engine import Card, Game, load_cards
from tools.generate_impacts import PROFILES, SAMPLE_RATE, generate


class DamageEventTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_cards(), seed=42, opening_hand=0)
        self.events = []
        self.game.on_damage = lambda amount: self.events.append(amount)

    def test_callback_runs_synchronously_after_health_change(self):
        target = self.game.players[1]
        snapshots = []
        self.game.on_damage = lambda amount: snapshots.append((amount, target.health))
        self.game.damage(target, 4)
        self.assertEqual(snapshots, [(4, 26)])

    def test_shield_zero_healing_and_destroy_do_not_play_impact(self):
        rook = self.game.summon(1, "torre")
        self.game.damage(rook, 3)
        self.game.damage(rook, 0)
        self.game.heal(rook, 1)
        self.game.parser.execute(
            [{"trigger": "on_play", "action": "destroy", "target": "all_enemy_minions"}],
            "on_play", 0,
        )
        self.assertEqual(self.events, [])

    def test_combat_and_retaliation_each_emit_at_damage_application(self):
        queen = self.game.summon(0, "dama")
        bishop = self.game.summon(1, "bispo")
        self.game.attack(0, queen, bishop)
        self.assertEqual(self.events, [6, 3])

    def test_area_effect_and_hero_damage(self):
        self.game.summon(1, "bispo")
        self.game.summon(1, "peao")
        self.game.parser.execute(
            [{"trigger": "on_play", "action": "damage", "amount": 1, "target": "all_enemies"}],
            "on_play", 0,
        )
        self.assertEqual(self.events, [1, 1, 1])

    def test_fatigue_and_lethal_damage_emit(self):
        self.game.players[0].deck.clear()
        self.game.draw_card(0)
        self.game.damage(self.game.hero_target(0), 99)
        self.game.cleanup()
        self.assertEqual(self.events, [1, 99])
        self.assertTrue(self.game.over)

    def test_spell_play_uses_same_damage_event(self):
        player = self.game.players[0]
        player.mana = 10
        self.game.summon(1, "bispo")
        self.game.summon(1, "bispo")
        card = Card(self.game.uid(), self.game.catalog["ataque_duplo"])
        player.hand.append(card)
        self.game.play_card(0, card)
        self.assertEqual(self.events, [2, 2])


class AudioTests(unittest.TestCase):
    def setUp(self):
        pygame.mixer.pre_init(44100, -16, 2, 256)
        pygame.init()
        self.addCleanup(pygame.quit)

    def test_wav_assets_have_expected_duration_and_no_clipping(self):
        for name, (duration, _, _) in PROFILES.items():
            with self.subTest(name=name), wave.open(str(IMPACTS_PATH / f"{name}.wav"), "rb") as stream:
                self.assertEqual(stream.getframerate(), SAMPLE_RATE)
                self.assertEqual(stream.getsampwidth(), 2)
                self.assertEqual(stream.getnchannels(), 1)
                samples = struct.unpack(f"<{stream.getnframes()}h", stream.readframes(stream.getnframes()))
                self.assertAlmostEqual(len(samples) / SAMPLE_RATE, duration, places=4)
                self.assertGreater(max(abs(s) for s in samples[:441]), 1000)
                self.assertLess(max(abs(s) for s in samples), 32767)
                self.assertEqual(samples[-1], 0)

    def test_assets_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            generate(Path(directory))
            for name in PROFILES:
                self.assertEqual(
                    (Path(directory) / f"{name}.wav").read_bytes(),
                    (IMPACTS_PATH / f"{name}.wav").read_bytes(),
                )

    def test_thresholds_and_nonblocking_channel_playback(self):
        audio = ImpactAudio()
        self.assertEqual(audio.error, "")
        self.assertGreaterEqual(pygame.mixer.get_num_channels(), 16)
        for amount, name in ((1, "light"), (2, "light"), (3, "medium"),
                             (4, "medium"), (5, "heavy"), (30, "heavy")):
            channel = Mock()
            with self.subTest(amount=amount), patch("audio.pygame.mixer.find_channel", return_value=channel) as find:
                audio.play_damage(amount)
                find.assert_called_once_with(force=True)
                channel.play.assert_called_once_with(audio.sounds[name])
        audio.play_damage(2)
        self.assertTrue(pygame.mixer.get_busy())

    def test_unavailable_audio_and_missing_assets_are_explicit(self):
        pygame.mixer.quit()
        audio = ImpactAudio()
        self.assertIn("Audio indisponivel", audio.error)
        audio.play_damage(3)
        pygame.mixer.init()
        with tempfile.TemporaryDirectory() as directory:
            audio = ImpactAudio(Path(directory))
        self.assertIn("erro ao carregar impactos", audio.error)
        self.assertEqual(audio.sounds, {})

    def test_app_wires_audio_to_current_game(self):
        from main import App

        with tempfile.TemporaryDirectory() as directory:
            app = App(decks_path=Path(directory) / "decks.json")
            self.addCleanup(app.puzzle_view.close)
            with patch.object(app.audio, "play_damage") as play:
                app.start_game()
                app.game.damage(app.game.hero_target(1), 2)
                play.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
