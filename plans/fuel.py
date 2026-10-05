"""
Optional, light food ideas around run days. Pure data.
Kept deliberately simple and non-prescriptive: easy runs under an hour don't need special fuel.
"""

BEFORE_RUN = [
    "2–3 dates",
    "1 small banana",
    "A slice of toast with honey or jam",
    "1–2 idlis",
    "A small bowl of poha",
    "A rice cake with a little peanut butter",
]

AFTER_RUN = [
    "A banana with a bowl of curd",
    "A glass of chaas (buttermilk)",
    "Eggs or paneer on toast",
    "A glass of milk or a smoothie",
    "A bowl of sprouts chaat",
    "Your normal meal, with a glass of water",
]

NOTE = (
    "Optional. Easy runs under an hour don't need special food, and running on an empty stomach "
    "is fine if it feels good. Drink some water either way. If you have allergies, diabetes or "
    "other dietary needs, follow your own doctor's advice."
)


def fuel_tip(seed: int) -> dict:
    """Two before-run ideas and one after-run idea, rotating by block index for variety."""
    n = len(BEFORE_RUN)
    return {
        "before": [BEFORE_RUN[seed % n], BEFORE_RUN[(seed + 3) % n]],
        "after": AFTER_RUN[seed % len(AFTER_RUN)],
        "note": NOTE,
    }
