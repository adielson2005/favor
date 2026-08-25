from decimal import Decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconcile import cents


def test_cents_avoids_binary_float_rounding():
    assert cents(10.01) == 1001
    assert cents("0.29") == 29


def test_cents_rounds_half_up_for_legacy_reais_values():
    assert cents(Decimal("1.005")) == 101
    assert cents(0) == 0
