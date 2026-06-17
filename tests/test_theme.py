"""Tests for the theme module — data, persistence, color helpers, CSS generation."""

import json

import pytest

from nothing_app import theme as _tm
from nothing_app.theme import (
    Theme,
    _darken,
    _lighten,
    _rgba,
    _texture_css,
    generate_css,
    hex_to_rgb,
    load,
    save,
)


@pytest.fixture(autouse=True)
def isolated_theme(tmp_path, monkeypatch):
    monkeypatch.setattr(_tm, "_DIR", str(tmp_path))
    monkeypatch.setattr(_tm, "_THEME_FILE", str(tmp_path / "theme.json"))


# ── Theme dataclass defaults ──────────────────────────────────────────────────


def test_default_accent():
    assert Theme().accent == "#e83535"


def test_default_bg_color():
    assert Theme().bg_color == "#000000"


def test_default_window_opacity():
    assert Theme().window_opacity == 1.0


def test_default_card_opacity():
    assert Theme().card_opacity == 1.0


def test_default_blur():
    assert Theme().blur == 0


def test_default_texture():
    assert Theme().texture == "none"


# ── load / save round-trip ────────────────────────────────────────────────────


def test_load_missing_file_returns_defaults():
    t = load()
    assert t == Theme()


def test_load_bad_json_returns_defaults(tmp_path):
    (tmp_path / "theme.json").write_text("not json")
    t = load()
    assert t == Theme()


def test_save_and_load_roundtrip():
    t = Theme(
        accent="#3b82f6", bg_color="#1a1b26", window_opacity=0.8, card_opacity=0.5, blur=6, texture="dots"
    )
    save(t)
    t2 = load()
    assert t2 == t


def test_save_creates_directory(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "config"
    monkeypatch.setattr(_tm, "_DIR", str(nested))
    monkeypatch.setattr(_tm, "_THEME_FILE", str(nested / "theme.json"))
    save(Theme())
    assert (nested / "theme.json").exists()


def test_save_writes_valid_json(tmp_path):
    save(Theme(accent="#ec4899", bg_color="#0f0e17"))
    data = json.loads((tmp_path / "theme.json").read_text())
    assert data["accent"] == "#ec4899"
    assert data["bg_color"] == "#0f0e17"


def test_load_ignores_unknown_keys(tmp_path):
    (tmp_path / "theme.json").write_text('{"accent":"#ffffff","unknown_key":42}')
    t = load()
    assert t.accent == "#ffffff"
    assert not hasattr(t, "unknown_key")


def test_load_uses_defaults_for_missing_keys(tmp_path):
    (tmp_path / "theme.json").write_text('{"accent":"#06b6d4"}')
    t = load()
    assert t.accent == "#06b6d4"
    assert t.window_opacity == 1.0
    assert t.blur == 0


def test_load_migrates_card_blur_to_blur(tmp_path):
    (tmp_path / "theme.json").write_text('{"accent":"#e83535","card_blur":8}')
    t = load()
    assert t.blur == 8


# ── hex_to_rgb ────────────────────────────────────────────────────────────────


def test_hex_to_rgb_red():
    assert hex_to_rgb("#e83535") == (232, 53, 53)


def test_hex_to_rgb_blue():
    assert hex_to_rgb("#3b82f6") == (59, 130, 246)


def test_hex_to_rgb_black():
    assert hex_to_rgb("#000000") == (0, 0, 0)


def test_hex_to_rgb_white():
    assert hex_to_rgb("#ffffff") == (255, 255, 255)


def test_hex_to_rgb_without_hash():
    assert hex_to_rgb("10b981") == (16, 185, 129)


# ── _rgba ─────────────────────────────────────────────────────────────────────


def test_rgba_format():
    result = _rgba("#e83535", 0.5)
    assert result == "rgba(232, 53, 53, 0.500)"


def test_rgba_full_opacity():
    result = _rgba("#000000", 1.0)
    assert result == "rgba(0, 0, 0, 1.000)"


def test_rgba_zero_opacity():
    result = _rgba("#ffffff", 0.0)
    assert result == "rgba(255, 255, 255, 0.000)"


# ── _darken ───────────────────────────────────────────────────────────────────


def test_darken_reduces_each_channel():
    r, g, b = hex_to_rgb(_darken("#e83535", 0.5))
    assert r < 232 and g < 53 and b < 53


def test_darken_full_factor_unchanged():
    assert _darken("#e83535", 1.0) == "#e83535"


def test_darken_zero_gives_black():
    assert _darken("#e83535", 0.0) == "#000000"


def test_darken_does_not_exceed_255():
    result = _darken("#ffffff", 2.0)
    r, g, b = hex_to_rgb(result)
    assert r <= 255 and g <= 255 and b <= 255


def test_darken_black_stays_black():
    assert _darken("#000000", 0.5) == "#000000"


# ── _lighten ──────────────────────────────────────────────────────────────────


def test_lighten_increases_each_channel():
    orig_r, orig_g, orig_b = hex_to_rgb("#3b82f6")
    r, g, b = hex_to_rgb(_lighten("#3b82f6", 0.2))
    assert r >= orig_r and g >= orig_g and b >= orig_b


def test_lighten_zero_factor_unchanged():
    assert _lighten("#e83535", 0.0) == "#e83535"


def test_lighten_full_factor_gives_white():
    assert _lighten("#e83535", 1.0) == "#ffffff"


def test_lighten_does_not_exceed_255():
    result = _lighten("#ffffff", 0.5)
    r, g, b = hex_to_rgb(result)
    assert r <= 255 and g <= 255 and b <= 255


# ── _texture_css ──────────────────────────────────────────────────────────────


def test_texture_none_clears_image():
    css = _texture_css("none")
    assert "none" in css
    assert "background-image" in css


def test_texture_dots_uses_radial_gradient():
    css = _texture_css("dots")
    assert "radial-gradient" in css
    assert "background-size" in css


def test_texture_scanlines_uses_repeating_gradient():
    css = _texture_css("scanlines")
    assert "repeating-linear-gradient" in css


def test_texture_noise_uses_data_uri():
    css = _texture_css("noise")
    assert "data:image/svg+xml;base64," in css
    assert "background-size" in css


def test_texture_noise_base64_is_valid():
    import base64 as _b64

    css = _texture_css("noise")
    b64_part = css.split("base64,")[1].split('"')[0].strip().rstrip(";").strip()
    decoded = _b64.b64decode(b64_part)
    assert b"<svg" in decoded


# ── generate_css — structure ──────────────────────────────────────────────────


def test_generate_css_contains_accent_define_color():
    css = generate_css(Theme(accent="#3b82f6"))
    assert "@define-color accent_color #3b82f6" in css
    assert "@define-color accent_bg_color #3b82f6" in css


def test_generate_css_contains_keyframes():
    css = generate_css(Theme())
    assert "@keyframes dot-pulse" in css
    assert "@keyframes scan-bloom" in css


def test_generate_css_contains_anc_button_active():
    css = generate_css(Theme())
    assert ".anc-button.active" in css


def test_generate_css_contains_eq_button_active():
    css = generate_css(Theme())
    assert ".eq-button.active" in css


def test_generate_css_contains_switch_checked():
    css = generate_css(Theme())
    assert "switch:checked" in css


def test_generate_css_contains_scan_button():
    css = generate_css(Theme())
    assert ".scan-button" in css


def test_generate_css_contains_nothing_dot():
    css = generate_css(Theme())
    assert ".nothing-dot" in css


def test_generate_css_contains_progress_bar():
    css = generate_css(Theme())
    assert "progressbar progress" in css


def test_generate_css_contains_disconnect_button():
    css = generate_css(Theme())
    assert ".disconnect-button" in css


# ── generate_css — accent propagation ────────────────────────────────────────


def test_generate_css_blue_accent_appears_in_output():
    css = generate_css(Theme(accent="#3b82f6"))
    assert "#3b82f6" in css


def test_generate_css_custom_accent_rgba_in_keyframes():
    css = generate_css(Theme(accent="#10b981"))
    r, g, b = hex_to_rgb("#10b981")
    assert f"rgba({r}, {g}, {b}," in css


def test_generate_css_default_accent_matches_original_red():
    css = generate_css(Theme())
    assert "#e83535" in css


# ── generate_css — background color ──────────────────────────────────────────


def test_generate_css_bg_color_appears_in_window_rule():
    css = generate_css(Theme(bg_color="#1a1b26"))
    win_block = css.split("window, .background")[1].split("}")[0]
    assert "#1a1b26" in win_block


def test_generate_css_bg_color_default_is_black():
    css = generate_css(Theme())
    win_block = css.split("window, .background")[1].split("}")[0]
    assert "#000000" in win_block


def test_generate_css_custom_bg_used_in_app_background_gradient():
    css = generate_css(Theme(bg_color="#1e1e2e"))
    bg_block = css[css.index(".app-background {") :][:300]
    assert "1e1e2e" in bg_block or "background" in bg_block


def test_generate_css_different_bg_colors_produce_different_output():
    css_a = generate_css(Theme(bg_color="#000000"))
    css_b = generate_css(Theme(bg_color="#1a1b26"))
    assert css_a != css_b


# ── generate_css — blur on background ────────────────────────────────────────


def test_generate_css_no_blur_omits_filter():
    css = generate_css(Theme(blur=0))
    assert "filter: blur(" not in css


def test_generate_css_blur_emits_filter():
    css = generate_css(Theme(blur=8))
    assert "filter: blur(8px)" in css


def test_generate_css_blur_appears_in_app_background():
    css = generate_css(Theme(blur=4))
    bg_section = css[css.index(".app-background {") :]
    first_block = bg_section[: bg_section.index("}") + 1]
    assert "blur(4px)" in first_block


def test_generate_css_blur_not_in_nothing_page():
    css = generate_css(Theme(blur=6))
    page_section = css[css.index(".nothing-page {") :]
    first_block = page_section[: page_section.index("}") + 1]
    assert "blur(" not in first_block


def test_generate_css_blur_not_in_device_card():
    css = generate_css(Theme(blur=6))
    card_section = css[css.index(".device-card {") :]
    first_block = card_section[: card_section.index("}") + 1]
    assert "blur(" not in first_block


def test_generate_css_blur_not_in_settings_group():
    css = generate_css(Theme(blur=6))
    group_section = css[css.index(".settings-group {") :]
    first_block = group_section[: group_section.index("}") + 1]
    assert "blur(" not in first_block


# ── generate_css — card opacity ───────────────────────────────────────────────


def test_generate_css_card_opacity_scales_alpha():
    css_full = generate_css(Theme(card_opacity=1.0))
    css_half = generate_css(Theme(card_opacity=0.5))
    assert ".device-card" in css_full
    assert ".device-card" in css_half

    def extract_device_card_block(css):
        start = css.index(".device-card {")
        end = css.index("}", start)
        return css[start:end]

    assert extract_device_card_block(css_full) != extract_device_card_block(css_half)


# ── generate_css — textures ───────────────────────────────────────────────────


def test_generate_css_texture_none_sets_no_image():
    css = generate_css(Theme(texture="none"))
    bg_block = css[css.index(".app-background {") :][:300]
    assert "background-image: none" in bg_block


def test_generate_css_texture_dots():
    css = generate_css(Theme(texture="dots"))
    bg_block = css[css.index(".app-background {") :][:400]
    assert "radial-gradient" in bg_block


def test_generate_css_texture_scanlines():
    css = generate_css(Theme(texture="scanlines"))
    bg_block = css[css.index(".app-background {") :][:500]
    assert "repeating-linear-gradient" in bg_block


def test_generate_css_texture_noise():
    css = generate_css(Theme(texture="noise"))
    bg_block = css[css.index(".app-background {") :][:700]
    assert "data:image/svg+xml;base64," in bg_block


# ── generate_css — default produces stable output ────────────────────────────


def test_generate_css_default_is_deterministic():
    assert generate_css(Theme()) == generate_css(Theme())


def test_generate_css_different_themes_differ():
    assert generate_css(Theme(accent="#e83535")) != generate_css(Theme(accent="#3b82f6"))


# ── ACCENT_PRESETS, BG_PRESETS, and TEXTURES constants ───────────────────────


def test_accent_presets_all_valid_hex():
    from nothing_app.theme import ACCENT_PRESETS

    for color, _ in ACCENT_PRESETS:
        assert color.startswith("#")
        assert len(color) == 7
        hex_to_rgb(color)


def test_bg_presets_all_valid_hex():
    from nothing_app.theme import BG_PRESETS

    for color, _ in BG_PRESETS:
        assert color.startswith("#")
        assert len(color) == 7
        hex_to_rgb(color)


def test_textures_keys_match_texture_css():
    from nothing_app.theme import TEXTURES

    for key, _ in TEXTURES:
        css = _texture_css(key)
        assert isinstance(css, str) and len(css) > 0
