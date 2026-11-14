"""Delayed card descriptions, keyword explanations and summoned-card previews."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from game_engine import KEYWORD_LABELS
from ui_theme import BLUE, GOLD, MUTED, PANEL, WHITE

if TYPE_CHECKING:
    from main import App


HOVER_DELAY_MS = 700
PANEL_WIDTH = 310
GAP = 8
PADDING = 12
KEYWORD_DESCRIPTIONS = {
    "charge": "Pode atacar imediatamente, inclusive o Rei.",
    "rush": "No turno em que entra, pode atacar peças, mas nao o Rei nem o Rei ativado.",
    "divine_shield": "Absorve a primeira instancia de dano positivo. Nao impede destruicao.",
    "windfury": "Pode atacar duas vezes por turno; ainda precisa esperar para atacar se nao tiver Iniciativa ou Desenvolvimento.",
    "elusive": "Nao pode ser selecionado manualmente por manobras. Ataques, efeitos de area, menor Vida e efeitos de entrada ainda funcionam.",
}
MECHANIC_LABELS = {
    "freeze": "Congelamento", "on_play": "Ao entrar",
    "on_death": "Ao morrer", "on_turn_start": "Inicio do turno",
    "on_turn_end": "Fim do turno", "on_kill": "Por abate",
}
MECHANIC_DESCRIPTIONS = {
    "freeze": "A peça nao pode atacar ate o fim do proximo turno do seu dono, incluindo o restante do turno atual.",
    "on_play": "O efeito acontece ao jogar a carta como peça; peças desenvolvidas por efeitos nao o executam.",
    "on_death": "O efeito acontece quando a peça morre, depois de remover as baixas simultaneas. A morte de um Rei encerra a partida antes destes efeitos.",
    "on_turn_start": "O efeito acontece no inicio do turno do dono da peça.",
    "on_turn_end": "O efeito acontece no fim do turno do dono da peça.",
    "on_kill": "O efeito acontece para cada alvo abatido. Proteção que absorve dano nao conta como abate.",
}


def card_details(card: dict, catalog: dict[str, dict]) -> tuple[list[str], list[dict]]:
    keywords = list(dict.fromkeys(card["piece_mode"]["keywords"]))
    for effect in card["piece_mode"]["effects"]:
        trigger = effect["trigger"]
        if trigger in MECHANIC_LABELS and trigger not in keywords:
            keywords.append(trigger)
    generated: list[dict] = []
    seen: set[str] = set()
    effects = [*card["piece_mode"]["effects"], *card["manouvre_mode"]["effects"]]
    while effects:
        effect = effects.pop(0)
        if effect["action"] == "grant_keyword" and effect["keyword"] not in keywords:
            keywords.append(effect["keyword"])
        if effect["action"] == "freeze" and "freeze" not in keywords:
            keywords.append("freeze")
        if effect["action"] == "summon" and effect["card_id"] not in seen:
            card_id = effect["card_id"]
            generated.append(catalog[card_id])
            seen.add(card_id)
        if "on_kill" in effect:
            if "on_kill" not in keywords:
                keywords.append("on_kill")
            effects.insert(0, effect["on_kill"])
    return keywords, generated


class CardTooltip:
    def __init__(self) -> None:
        self.key: object | None = None
        self.card: dict | None = None
        self.anchor = pygame.Rect(0, 0, 0, 0)
        self.since = 0
        self.visible = False
        self.scroll = 0
        self.max_scroll = 0

    def update(self, key: object | None, card: dict | None, anchor: pygame.Rect | None, now: int) -> None:
        if key != self.key:
            self.key = key
            self.since = now
            self.scroll = 0
            self.max_scroll = 0
        self.card = card
        if anchor is not None:
            self.anchor = anchor.copy()
        self.visible = key is not None and now - self.since >= HOVER_DELAY_MS

    def reset(self) -> None:
        self.update(None, None, None, 0)

    def wheel(self, amount: int) -> bool:
        if not self.visible or not self.max_scroll:
            return False
        self.scroll = max(0, min(self.max_scroll, self.scroll - amount * 60))
        return True

    @staticmethod
    def panel(
        app: App, title: str, text: str, subtitle: str = "",
        art: pygame.Surface | None = None,
    ) -> pygame.Surface:
        font = app.font
        lines = app.wrap(text, PANEL_WIDTH - 2 * PADDING, font)
        title_lines = app.wrap(title, PANEL_WIDTH - 2 * PADDING, font)
        subtitle_lines = app.wrap(subtitle, PANEL_WIDTH - 2 * PADDING, app.small) if subtitle else []
        height = 2 * PADDING + len(title_lines) * font.get_linesize()
        height += len(subtitle_lines) * app.small.get_linesize()
        height += art.get_height() + 6 if art else 0
        height += 6 + len(lines) * font.get_linesize()
        surface = pygame.Surface((PANEL_WIDTH, height), pygame.SRCALPHA)
        pygame.draw.rect(surface, PANEL, surface.get_rect(), border_radius=6)
        pygame.draw.rect(surface, GOLD, surface.get_rect(), 2, border_radius=6)
        y = PADDING
        for line in title_lines:
            app.text(line, (PADDING, y), GOLD, font, surface=surface)
            y += font.get_linesize()
        for line in subtitle_lines:
            app.text(line, (PADDING, y), BLUE, app.small, surface=surface)
            y += app.small.get_linesize()
        if art:
            surface.blit(art, (PADDING, y + 3))
            y += art.get_height() + 6
        y += 6
        for line in lines:
            app.text(line, (PADDING, y), WHITE, font, surface=surface)
            y += font.get_linesize()
        return surface

    def draw(self, app: App) -> None:
        if not self.visible or self.card is None:
            return
        catalog = {card["id"]: card for card in app.cards}
        if app.game is not None:
            catalog.update(app.game.catalog)
        keywords, generated = card_details(self.card, catalog)
        columns = [[self.panel(app, self.card["name"], self.card["description"])]]
        if keywords:
            columns.append([
                self.panel(
                    app, KEYWORD_LABELS[keyword] if keyword in KEYWORD_LABELS else MECHANIC_LABELS[keyword],
                    KEYWORD_DESCRIPTIONS[keyword] if keyword in KEYWORD_DESCRIPTIONS else MECHANIC_DESCRIPTIONS[keyword],
                )
                for keyword in keywords
            ])
        if generated:
            columns.append([
                self.panel(
                    app, card["name"], card["description"],
                    f"Peça desenvolvida | {card['piece_mode']['cost']} tempo | "
                    f"{card['piece_mode']['attack']}/{card['piece_mode']['health']}",
                    app.card_art(card, (65, 77)),
                )
                for card in generated
            ])
        heights = [sum(panel.get_height() for panel in column) + GAP * (len(column) - 1) for column in columns]
        width = len(columns) * PANEL_WIDTH + (len(columns) - 1) * GAP
        content_height = max(heights)
        screen = app.screen.get_rect()
        footer = app.small.get_linesize() + 4 if content_height > screen.height - 24 else 0
        height = min(content_height, screen.height - 24 - footer)
        self.max_scroll = max(0, content_height - height)
        self.scroll = min(self.scroll, self.max_scroll)
        x = max(12, min(self.anchor.left, screen.width - width - 12))
        y = self.anchor.top - height - footer - GAP
        if y < 12:
            y = min(self.anchor.bottom + GAP, screen.height - height - footer - 12)
        viewport = pygame.Rect(x, y, width, height)
        old_clip = app.screen.get_clip()
        app.screen.set_clip(viewport.clip(old_clip))
        for index, column in enumerate(columns):
            top = y - self.scroll
            for panel in column:
                app.screen.blit(panel, (x + index * (PANEL_WIDTH + GAP), top))
                top += panel.get_height() + GAP
        app.screen.set_clip(old_clip)
        if self.max_scroll:
            pygame.draw.rect(app.screen, PANEL, (viewport.x, viewport.bottom, width, footer))
            app.text("Role para ver mais", (viewport.x + PADDING, viewport.bottom + 2), MUTED, app.small)


class InfoTooltip:
    def __init__(self) -> None:
        self.key: object | None = None
        self.title = ""
        self.text = ""
        self.anchor = pygame.Rect(0, 0, 0, 0)
        self.since = 0
        self.visible = False

    def update(
        self, key: object | None, title: str, text: str,
        anchor: pygame.Rect | None, now: int,
    ) -> None:
        if key != self.key:
            self.since = now
        self.key, self.title, self.text = key, title, text
        if anchor is not None:
            self.anchor = anchor.copy()
        self.visible = key is not None and now - self.since >= HOVER_DELAY_MS

    def reset(self) -> None:
        self.update(None, "", "", None, 0)

    def draw(self, app: App) -> None:
        if not self.visible:
            return
        panel = CardTooltip.panel(app, self.title, self.text)
        screen = app.screen.get_rect()
        x = max(0, min(self.anchor.left, screen.width - panel.get_width()))
        y = self.anchor.top - panel.get_height() - GAP
        if y < 0:
            y = min(self.anchor.bottom + GAP, screen.height - panel.get_height())
        app.screen.blit(panel, (x, y))
