import pytest

from app.services.risk_profile import _indian_grouping, _rupees


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "0"),
        (5, "5"),
        (100, "100"),
        (999, "999"),
        (1000, "1,000"),
        (25000, "25,000"),
        (100000, "1,00,000"),
        (1200000, "12,00,000"),
        (12000000, "1,20,00,000"),
        (100000000, "10,00,00,000"),
        (-25000, "-25,000"),
    ],
)
def test_indian_grouping(n, expected):
    assert _indian_grouping(n) == expected


def test_rupees_formats_paise_as_whole_rupees_with_indian_grouping():
    assert _rupees(25_000_00) == "Rs 25,000"
    assert _rupees(12_000_000_00) == "Rs 1,20,00,000"


def test_rupees_truncates_leftover_paise():
    assert _rupees(150) == "Rs 1"  # 150 paise = Rs 1.50, floor to whole rupees
