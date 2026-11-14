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

from audio import EVENT_SOUNDS, IMPACTS_PATH, ImpactAudio
from game_engine import Card, Game, RuleError, load_cards
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
            [{"trigger": "on_play", "action": "destroy", "target": "all_enemy_pieces"}],
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

    def test_maneuver_play_uses_same_damage_event(self):
        player = self.game.players[0]
        player.mana = 10
        self.game.summon(1, "bispo")
        self.game.summon(1, "bispo")
        card = Card(self.game.uid(), self.game.catalog["ataque_duplo"])
        player.hand.append(card)
        self.game.play_card(0, card, mode="manobra")
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

    def test_event_assets_load_and_play_without_blocking(self):
        audio = ImpactAudio()
        self.assertEqual(audio.error, "")
        self.assertEqual(set(audio.event_sounds), set(EVENT_SOUNDS))
        for event, sound in audio.event_sounds.items():
            channel = Mock()
            with self.subTest(event=event), patch("audio.pygame.mixer.find_channel", return_value=channel):
                audio.play_event(event)
                channel.play.assert_called_once_with(sound)

    def test_missing_event_asset_preserves_other_sounds_and_reports_failure(self):
        original = pygame.mixer.Sound

        def load(path):
            if path.endswith(EVENT_SOUNDS["freeze"]):
                raise pygame.error("invalid sound")
            return original(path)

        with patch("audio.pygame.mixer.Sound", side_effect=load):
            audio = ImpactAudio()
        self.assertIn(EVENT_SOUNDS["freeze"], audio.error)
        self.assertNotIn("freeze", audio.event_sounds)
        self.assertIn("draw", audio.event_sounds)
        self.assertIn("light", audio.sounds)

    def test_button_press_release_and_victory_only_once(self):
        from main import App, State

        with tempfile.TemporaryDirectory() as directory:
            app = App(decks_path=Path(directory) / "decks.json")
            self.addCleanup(app.puzzle_view.close)
            app.start_game()
            with patch.object(app.audio, "play_event") as play:
                app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=app.end_button.center))
                app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=app.end_button.center))
                events = [call.args[0] for call in play.call_args_list]
                self.assertEqual(events.count("end_turn_down"), 1)
                self.assertEqual(events.count("end_turn_up"), 1)
                app.game.over = True
                app.game.winner = 0
                app.update()
                app.update()
                self.assertEqual(app.state, State.GAME_OVER)
                self.assertEqual([call.args[0] for call in play.call_args_list].count("victory"), 1)

    def test_defeat_and_draw_do_not_play_victory(self):
        from main import App

        with tempfile.TemporaryDirectory() as directory:
            app = App(decks_path=Path(directory) / "decks.json")
            self.addCleanup(app.puzzle_view.close)
            with patch.object(app.audio, "play_event") as play:
                for winner in (1, None):
                    app.start_game()
                    app.game.over = True
                    app.game.winner = winner
                    app.update()
                self.assertNotIn("victory", [call.args[0] for call in play.call_args_list])


class GameSoundEventTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.game = Game(load_cards(), seed=42, opening_hand=2, on_event=self.events.append)

    def test_opening_shuffle_deals_and_turn_sounds(self):
        self.assertEqual(self.events, [
            "shuffle", "opening_deal", "opening_deal", "opening_deal", "opening_deal",
            "mana_add", "mana_refresh", "your_turn", "draw",
        ])

    def test_draw_only_when_card_enters_hand(self):
        player = self.game.players[0]
        self.events.clear()
        self.game.draw_card(0)
        self.assertEqual(self.events, ["draw"])
        while len(player.hand) < 10:
            player.hand.append(Card(self.game.uid(), self.game.catalog["peao"]))
        self.events.clear()
        self.game.draw_card(0)
        self.assertEqual(self.events, [])

    def test_mana_sound_only_for_successful_costs(self):
        player = self.game.players[0]
        player.mana = 10
        card = Card(self.game.uid(), self.game.catalog["peao"])
        player.hand.append(card)
        self.events.clear()
        self.game.play_card(0, card, position=0)
        self.assertEqual(self.events, ["mana_expend"])
        self.events.clear()
        unit = player.unit_at(0)
        self.game.move_unit(0, unit, 1)
        self.assertEqual(self.events, ["mana_expend"])
        self.events.clear()
        with self.assertRaises(RuleError):
            self.game.move_unit(0, unit, 1)
        self.assertEqual(self.events, [])
        self.game.summon(0, "torre", 5)
        self.game.castle(0)
        self.assertEqual(self.events, ["mana_expend"])

    def test_turn_alert_only_on_human_turn_and_no_add_at_cap(self):
        self.events.clear()
        self.game.end_turn(0)
        self.assertIn("mana_refresh", self.events)
        self.assertNotIn("your_turn", self.events)
        self.game.players[0].max_mana = 10
        self.events.clear()
        self.game.end_turn(1)
        self.assertIn("your_turn", self.events)
        self.assertIn("mana_refresh", self.events)
        self.assertNotIn("mana_add", self.events)

    def test_freeze_once_per_effect_only_when_target_hit(self):
        self.events.clear()
        effect = {"action": "freeze", "target": "all_enemy_pieces", "amount": 1}
        self.game.parser.execute_action(effect, 0)
        self.assertEqual(self.events, [])
        self.game.summon(1, "peao", 0)
        self.game.summon(1, "torre", 1)
        self.game.parser.execute_action(effect, 0)
        self.assertEqual(self.events, ["freeze"])


if __name__ == "__main__":
    unittest.main()
