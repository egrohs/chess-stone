import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deck_store import DeckStore
from game_engine import Game, load_cards


class DeckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "data" / "decks.json"
        self.cards = load_cards()
        self.store = DeckStore([card["id"] for card in self.cards], self.path)

    def test_roundtrip_multiple_decks_and_unlimited_copies(self):
        self.assertEqual(self.store.load(), {})
        decks = {"Peoes": ["peao"] * 45, "Teste": ["bispo", "dama"]}
        self.store.save(decks)
        self.assertEqual(self.store.load(), decks)
        decks["Teste"] = ["torre"]
        self.store.save(decks)
        self.assertEqual(self.store.load(), decks)

    def test_invalid_decks_do_not_overwrite_file(self):
        self.store.save({"Original": ["peao"]})
        original = self.path.read_bytes()
        for value in ([], {"": ["peao"]}, {"Vazio": []}, {"Erro": ["missing"]},
                      {"Nome": [1]}, {"x" * 41: ["peao"]}, {" Nome ": ["peao"]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.save(value)
            self.assertEqual(self.path.read_bytes(), original)

    def test_malformed_file_reports_error(self):
        self.path.parent.mkdir()
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.load()

    def test_failed_replace_preserves_file_and_cleans_temporary(self):
        self.store.save({"Original": ["peao"]})
        original = self.path.read_bytes()
        with patch("deck_store.os.replace", side_effect=OSError("sem permissao")):
            with self.assertRaises(OSError):
                self.store.save({"Novo": ["dama"]})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_custom_composition_and_smaller_opening_hand(self):
        deck = ["peao"] * 12 + ["torre"] * 3
        original = list(deck)
        game = Game(self.cards, player_deck=deck, deck_size=30, seed=3)
        player, enemy = game.players
        composition = player.deck + [c.definition["id"] for c in player.hand]
        self.assertCountEqual(composition, original)
        self.assertEqual(deck, original)
        self.assertEqual(len(enemy.deck) + len(enemy.hand), 30)
        small = Game(self.cards, player_deck=["dama"], seed=3)
        self.assertEqual(len(small.players[0].hand), 1)
        self.assertEqual(len(small.players[1].hand), 3)
        self.assertIsNotNone(small.players[0].king)

    def test_invalid_engine_decks_and_reproducibility(self):
        for deck in ([], ["missing"], [42], "peao"):
            with self.subTest(deck=deck), self.assertRaises(ValueError):
                Game(self.cards, player_deck=deck)
        deck = ["peao", "bispo", "dama", "torre"] * 5
        first = Game(self.cards, player_deck=deck, seed=42)
        second = Game(self.cards, player_deck=deck, seed=42)
        self.assertEqual(first.players[0].deck, second.players[0].deck)


if __name__ == "__main__":
    unittest.main()
