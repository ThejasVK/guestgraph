"""Did the campaign work? Holdout-based lift.

Before activating an audience, a fixed slice of it is held out and never sent to the ad
platform. Afterwards, compare how many guests in each group came back. The holdout is
picked by hashing the guest ID, so the same guest always lands in the same group and the
split can be reproduced later.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass


def in_holdout(guest_id: str, campaign: str, holdout_pct: float = 0.15) -> bool:
    h = int(hashlib.sha256(f"{campaign}:{guest_id}".encode()).hexdigest()[:8], 16)
    return (h % 10_000) / 10_000 < holdout_pct


@dataclass
class LiftReport:
    campaign: str
    exposed: int
    holdout: int
    exposed_rate: float
    holdout_rate: float
    absolute_lift: float
    relative_lift: float
    z: float
    p_value: float

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def text(self) -> str:
        verdict = "statistically significant" if self.significant else "not significant yet"
        return (f"{self.campaign}: {self.exposed_rate:.1%} of exposed guests returned vs "
                f"{self.holdout_rate:.1%} of the holdout ({self.relative_lift:+.0%} relative lift, "
                f"p={self.p_value:.3f}, {verdict}; n={self.exposed}+{self.holdout})")


def required_n_per_group(base_rate: float, relative_lift: float) -> int:
    """Guests needed in EACH group to detect this lift (two-sided alpha 0.05, 80% power)."""
    p1, p2 = base_rate, base_rate * (1 + relative_lift)
    z_a, z_b = 1.96, 0.8416
    return math.ceil((z_a + z_b) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2)


def lift(campaign: str, outcomes: dict[str, bool], holdout_pct: float = 0.15) -> LiftReport:
    """outcomes: guest_id -> returned within the measurement window."""
    e_n = e_y = h_n = h_y = 0
    for gid, returned in outcomes.items():
        if in_holdout(gid, campaign, holdout_pct):
            h_n += 1
            h_y += returned
        else:
            e_n += 1
            e_y += returned
    pe = e_y / e_n if e_n else 0.0
    ph = h_y / h_n if h_n else 0.0
    pooled = (e_y + h_y) / (e_n + h_n) if (e_n + h_n) else 0.0
    se = math.sqrt(pooled * (1 - pooled) * (1 / e_n + 1 / h_n)) if e_n and h_n and 0 < pooled < 1 else 0.0
    z = (pe - ph) / se if se else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))  # two-sided
    return LiftReport(campaign, e_n, h_n, pe, ph, pe - ph, (pe / ph - 1) if ph else 0.0, z, p)


def simulate_outcomes(guest_ids: list[str], campaign: str, base_rate: float = 0.30,
                      true_lift: float = 0.25, holdout_pct: float = 0.15, seed: int = 11) -> dict[str, bool]:
    """Synthetic post-campaign visits with a known effect, to check the method recovers it."""
    rng = random.Random(seed)
    out = {}
    for gid in guest_ids:
        rate = base_rate if in_holdout(gid, campaign, holdout_pct) else base_rate * (1 + true_lift)
        out[gid] = rng.random() < rate
    return out
