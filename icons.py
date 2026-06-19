"""Ícones vetoriais gerados com PIL para uso no CustomTkinter."""

from PIL import Image, ImageDraw
import customtkinter as ctk

_S = 18

def _mk(fn, s=_S) -> ctk.CTkImage:
    dark  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    light = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    fn(ImageDraw.Draw(dark),  "#f1f5f9")
    fn(ImageDraw.Draw(light), "#1e293b")
    return ctk.CTkImage(light_image=light, dark_image=dark, size=(s, s))


def add(s=_S):
    def draw(d, c):
        m, t = s // 2, max(1, s // 9)
        d.rectangle([m - t, 2, m + t, s - 3], fill=c)
        d.rectangle([2, m - t, s - 3, m + t], fill=c)
    return _mk(draw, s)


def folder(s=_S):
    def draw(d, c):
        tab_h = s // 3
        d.rounded_rectangle([1, tab_h, s // 2, tab_h + 2], radius=1, fill=c)
        d.rounded_rectangle([1, tab_h, s - 2, s - 2], radius=2, outline=c, width=2)
    return _mk(draw, s)


def save(s=_S):
    def draw(d, c):
        d.rounded_rectangle([2, 2, s - 3, s - 3], radius=2, outline=c, width=2)
        d.rectangle([5, 2, s - 6, s // 2 - 1], fill=c)
        d.rounded_rectangle([5, s // 2 + 1, s - 6, s - 5], radius=1, fill=c)
        mid = s // 2 - 3
        d.rectangle([mid, 4, mid + 2, s // 2 - 2], fill=(0, 0, 0, 0))
    return _mk(draw, s)


def trash(s=_S):
    def draw(d, c):
        m = s // 2
        d.line([2, 4, s - 3, 4], fill=c, width=2)
        d.line([m - 2, 2, m + 2, 2], fill=c, width=2)
        d.rounded_rectangle([3, 5, s - 4, s - 2], radius=2, outline=c, width=2)
        d.line([m, 8, m, s - 5], fill=c, width=1)
    return _mk(draw, s)


def export_icon(s=_S):
    def draw(d, c):
        m = s // 2
        d.rounded_rectangle([2, m, s - 3, s - 3], radius=2, outline=c, width=2)
        d.line([m, 2, m, m - 1], fill=c, width=2)
        d.polygon([(m, 1), (m - 4, 6), (m + 4, 6)], fill=c)
    return _mk(draw, s)


def play(s=_S):
    def draw(d, c):
        d.polygon([(3, 2), (3, s - 3), (s - 3, s // 2)], fill=c)
    return _mk(draw, s)


def pause(s=_S):
    def draw(d, c):
        t = max(2, s // 5)
        d.rectangle([3, 3, 3 + t, s - 4], fill=c)
        d.rectangle([s - 4 - t, 3, s - 4, s - 4], fill=c)
    return _mk(draw, s)


def stop(s=_S):
    def draw(d, c):
        d.rounded_rectangle([3, 3, s - 4, s - 4], radius=2, fill=c)
    return _mk(draw, s)


def close(s=_S):
    def draw(d, c):
        w = max(1, s // 9)
        d.line([3, 3, s - 4, s - 4], fill=c, width=w + 1)
        d.line([s - 4, 3, 3, s - 4], fill=c, width=w + 1)
    return _mk(draw, s)


def chart(s=_S):
    def draw(d, c):
        d.rectangle([1, s - 5, 4, s - 3], fill=c)
        d.rectangle([6, s // 2 - 1, 9, s - 3], fill=c)
        d.rectangle([11, 3, 14, s - 3], fill=c)
        d.line([1, s - 3, s - 2, s - 3], fill=c, width=1)
    return _mk(draw, s)


def refresh(s=_S):
    def draw(d, c):
        from PIL import ImageDraw as ID
        m = s // 2
        d.arc([2, 2, s - 3, s - 3], start=40, end=320, fill=c, width=2)
        d.polygon([(s - 4, 3), (s - 4, 8), (s - 9, 5)], fill=c)
    return _mk(draw, s)


def bolt(s=24):
    def draw(d, c):
        mx = s // 2
        d.polygon([
            (mx + 3, 1),
            (mx - 4, s // 2),
            (mx + 1, s // 2),
            (mx - 3, s - 1),
            (mx + 4, s // 2),
            (mx - 1, s // 2),
        ], fill=c)
    return _mk(draw, s)


def msg(s=_S):
    def draw(d, c):
        d.rounded_rectangle([1, 1, s - 2, s - 5], radius=3, outline=c, width=2)
        d.polygon([(3, s - 5), (3, s - 1), (8, s - 5)], fill=c)
    return _mk(draw, s)
