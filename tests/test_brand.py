import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_theme_uses_deck_hex_values():
    theme = (ROOT / ".streamlit" / "config.toml").read_text()
    for color in ("#164DFF", "#FFFFFF", "#E8EDFF", "#061242"):
        assert color in theme
    assert 'font = "sans serif"' in theme


def test_icon_is_square_transparent_png():
    data = (ROOT / "assets" / "easypost-icon.png").read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    width, height, _depth, color_type = struct.unpack(">IIBB", data[16:26])
    assert color_type == 6
    assert width == height
    assert width >= 256


def test_logo_is_transparent_png():
    data = (ROOT / "assets" / "easypost-logo.png").read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    width, height, _depth, color_type = struct.unpack(">IIBB", data[16:26])
    assert color_type == 6  # RGBA
    assert width >= 1000
    assert height >= 200
