import pytest

from elementor_mcp.core.normalizer.color_distance import delta_e


def test_identical_hex_delta_zero():
    assert delta_e("#FF0000", "#FF0000") == pytest.approx(0, abs=0.01)


def test_close_colors_small_delta():
    # Very close reds — should be < 5
    assert delta_e("#FF0000", "#FE0101") == pytest.approx(0, abs=2.0)


def test_far_colors_large_delta():
    # Red vs cyan — should be very large
    assert delta_e("#FF0000", "#00FFFF") > 60


def test_case_insensitive_hex():
    assert delta_e("#ff0000", "#FF0000") == pytest.approx(0, abs=0.01)


def test_invalid_hex_raises():
    with pytest.raises(ValueError):
        delta_e("not-a-color", "#FF0000")
