"""Time-based hand motion and matching hit testing, independent of game rules."""

from __future__ import annotations

from dataclasses import dataclass
import math

import pygame

from game_engine import Card


CARD_SIZE = (99, 196)


@dataclass
class CardMotion:
    x: float
    y: float
    focus: float = 0.0
    angle: float = 0.0

    @property
    def scale(self) -> float:
        return 1.0 + 0.32 * self.focus

    def contains(self, point: tuple[int, int]) -> bool:
        local = pygame.Vector2(point) - (self.x, self.y)
        local.rotate_ip(self.angle)
        return (
            abs(local.x) <= CARD_SIZE[0] * self.scale / 2
            and abs(local.y) <= CARD_SIZE[1] * self.scale / 2
        )


class HandView:
    def __init__(self) -> None:
        self.motions: dict[int, CardMotion] = {}
        self.hovered: Card | None = None

    def sync(self, cards: list[tuple[Card, pygame.Rect]]) -> None:
        active = {card.uid for card, _ in cards}
        self.motions = {uid: motion for uid, motion in self.motions.items() if uid in active}
        for card, rect in cards:
            self.motions.setdefault(card.uid, CardMotion(*rect.center))
        if self.hovered and self.hovered.uid not in active:
            self.hovered = None

    def layers(
        self, cards: list[tuple[Card, pygame.Rect]], selected: Card | None,
    ) -> list[tuple[Card, CardMotion]]:
        self.sync(cards)
        ordered = sorted(cards, key=lambda item: (
            item[0] is self.hovered, item[0] is selected,
        ))
        return [(card, self.motions[card.uid]) for card, _ in ordered]

    def card_at(
        self, cards: list[tuple[Card, pygame.Rect]], point: tuple[int, int],
        selected: Card | None,
    ) -> Card | None:
        anchors = {card.uid: rect for card, rect in cards}
        for card, motion in reversed(self.layers(cards, selected)):
            # Keep the original slot active so lifting away from the cursor
            # cannot repeatedly toggle hover at the bottom of the hand.
            if motion.contains(point) or (card is self.hovered and anchors[card.uid].collidepoint(point)):
                return card
        return None

    def update(
        self, cards: list[tuple[Card, pygame.Rect]], point: tuple[int, int],
        dt: float, selected: Card | None,
    ) -> None:
        self.hovered = self.card_at(cards, point, selected)
        # Exponential lerp has the same response at 30, 60 or 144 FPS.
        blend = -math.expm1(-16.0 * max(0.0, dt))
        for card, rect in cards:
            motion = self.motions[card.uid]
            hovered = card is self.hovered
            focus = 1.0 if hovered else 0.35 if card is selected else 0.0
            tilt = max(-1.0, min(1.0, (point[0] - motion.x) / 65)) if hovered else 0.0
            targets = (rect.centerx, rect.centery - 20 * focus, focus, -3.0 * tilt)
            motion.x += (targets[0] - motion.x) * blend
            motion.y += (targets[1] - motion.y) * blend
            motion.focus += (targets[2] - motion.focus) * blend
            motion.angle += (targets[3] - motion.angle) * blend
