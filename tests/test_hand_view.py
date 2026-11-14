import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from game_engine import Card
from hand_view import CARD_SIZE, CardMotion, HandView


class HandViewTests(unittest.TestCase):
    def setUp(self):
        self.cards = [
            (Card(i, {}), pygame.Rect(24 + i * 105, 718, *CARD_SIZE))
            for i in range(10)
        ]
        self.view = HandView()

    def test_hover_lifts_and_enlarges_then_returns_smoothly(self):
        card, rect = self.cards[3]
        self.view.update(self.cards, rect.center, 1 / 60, None)
        motion = self.view.motions[card.uid]
        self.assertIs(self.view.hovered, card)
        self.assertGreater(motion.focus, 0)
        self.assertLess(motion.focus, 1)
        self.assertLess(motion.y, rect.centery)
        self.assertGreater(motion.scale, 1)
        old_y, old_scale = motion.y, motion.scale
        self.view.update(self.cards, (0, 0), 1 / 60, None)
        self.assertIsNone(self.view.hovered)
        self.assertGreater(motion.y, old_y)
        self.assertLess(motion.y, rect.centery)
        self.assertLess(motion.scale, old_scale)
        for _ in range(60):
            self.view.update(self.cards, (0, 0), 1 / 60, None)
        self.assertAlmostEqual(motion.focus, 0, places=6)
        self.assertAlmostEqual(motion.y, rect.centery, places=4)

    def test_interpolation_is_independent_of_fps(self):
        card, rect = self.cards[0]
        results = []
        for fps in (30, 60, 144):
            view = HandView()
            for _ in range(fps):
                view.update(self.cards, rect.center, 1 / fps, None)
            results.append(view.motions[card.uid])
        for motion in results[1:]:
            self.assertAlmostEqual(motion.y, results[0].y, places=9)
            self.assertAlmostEqual(motion.focus, results[0].focus, places=9)

    def test_bottom_of_original_slot_keeps_hover_stable(self):
        card, rect = self.cards[0]
        point = (rect.centerx, rect.bottom - 2)
        for _ in range(120):
            self.view.update(self.cards, point, 1 / 60, None)
            self.assertIs(self.view.hovered, card)
        self.assertGreater(self.view.motions[card.uid].focus, 0.99)
        self.view.update(self.cards, (0, 0), 1 / 60, None)
        self.assertIsNone(self.view.hovered)

    def test_topmost_transformed_card_receives_click(self):
        card, rect = self.cards[3]
        self.view.update(self.cards, rect.center, 1, None)
        motion = self.view.motions[card.uid]
        point = (rect.centerx, round(motion.y - CARD_SIZE[1] * motion.scale / 2 + 10))
        self.assertFalse(rect.collidepoint(point))
        self.assertIs(self.view.card_at(self.cards, point, None), card)
        self.assertIs(self.view.layers(self.cards, None)[-1][0], card)

    def test_pointer_can_switch_between_adjacent_cards(self):
        for card, rect in self.cards:
            self.view.update(self.cards, rect.center, 0.25, None)
            self.assertIs(self.view.hovered, card)

    def test_rotation_hit_test_excludes_empty_bounding_box_corners(self):
        motion = CardMotion(200, 200, focus=1, angle=3)
        inside = pygame.Vector2(10, -110).rotate(-motion.angle) + (motion.x, motion.y)
        outside = pygame.Vector2(68, 0).rotate(-motion.angle) + (motion.x, motion.y)
        self.assertTrue(motion.contains((inside.x, inside.y)))
        self.assertFalse(motion.contains((outside.x, outside.y)))

    def test_selection_stays_raised_but_below_hovered_card(self):
        selected, _ = self.cards[0]
        hovered, rect = self.cards[1]
        self.view.update(self.cards, rect.center, 1, selected)
        self.assertAlmostEqual(self.view.motions[selected.uid].focus, 0.35, places=5)
        self.assertEqual([card for card, _ in self.view.layers(self.cards, selected)][-2:], [selected, hovered])

    def test_removed_cards_are_cleaned_up_and_remaining_cards_reflow(self):
        removed, rect = self.cards[0]
        self.view.update(self.cards, rect.center, 1, None)
        remaining, old_rect = self.cards[1]
        new_cards = [(remaining, rect)]
        self.view.update(new_cards, (0, 0), 1 / 60, None)
        self.assertEqual(set(self.view.motions), {remaining.uid})
        self.assertIsNone(self.view.hovered)
        self.assertGreater(self.view.motions[remaining.uid].x, rect.centerx)
        self.assertLess(self.view.motions[remaining.uid].x, old_rect.centerx)
        self.view.update([], (0, 0), 1, None)
        self.assertEqual(self.view.motions, {})

    def test_zero_and_negative_dt_do_not_move_cards(self):
        card, rect = self.cards[0]
        for dt in (0, -1):
            self.view.update(self.cards, rect.center, dt, None)
            motion = self.view.motions[card.uid]
            self.assertEqual((motion.x, motion.y, motion.focus), (*rect.center, 0))

    def test_tilt_is_bounded_and_full_hand_stays_on_screen(self):
        for card, rect in self.cards:
            view = HandView()
            view.update(self.cards, (rect.right - 1, rect.centery), 1, None)
            motion = view.motions[card.uid]
            self.assertLess(motion.angle, 0)
            self.assertGreaterEqual(motion.angle, -3)
            image = pygame.transform.rotozoom(
                pygame.Surface(CARD_SIZE), motion.angle, motion.scale,
            )
            bounds = image.get_rect(center=(round(motion.x), round(motion.y)))
            self.assertGreaterEqual(bounds.left, 0)
            self.assertLessEqual(bounds.right, 1100)
            self.assertGreaterEqual(bounds.top, 660)
            self.assertLessEqual(bounds.bottom, 940)


if __name__ == "__main__":
    unittest.main()
