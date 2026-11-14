"""Shared geometry of each player's fixed board slots."""

BOARD_LIMIT = 6
CORNER_SLOTS = (0, BOARD_LIMIT - 1)
EDGE_SLOTS = (1, BOARD_LIMIT - 2)
CENTER_SLOTS = range(2, BOARD_LIMIT - 2)
