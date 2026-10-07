"""Tests for the click-through window outline overlay."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from docking.platform.backends.base import Rect

gtk_ui = pytest.importorskip("docking.ui.window_outline")


class TestWindowOutlineHandlers:
    def test_constructor_sets_empty_input_shape(self, monkeypatch):
        shapes = []
        monkeypatch.setattr(
            gtk_ui.WindowOutline,
            "input_shape_combine_region",
            lambda _self, region: shapes.append(region),
        )

        outline = gtk_ui.WindowOutline()
        outline.destroy()

        assert len(shapes) == 1
        assert shapes[0].is_empty()

    def test_draw_strokes_inset_rectangle_border_only(self):
        widget = MagicMock()
        widget.get_allocated_width.return_value = 300
        widget.get_allocated_height.return_value = 200
        cr = MagicMock()

        handled = gtk_ui.WindowOutline._on_draw(widget, cr)

        assert handled is True
        half = gtk_ui.OUTLINE_WIDTH_PX / 2
        cr.rectangle.assert_called_once_with(
            half,
            half,
            300 - gtk_ui.OUTLINE_WIDTH_PX,
            200 - gtk_ui.OUTLINE_WIDTH_PX,
        )
        cr.stroke.assert_called_once()
        cr.fill.assert_not_called()


class TestWindowOutlineWidget:
    def test_show_around_places_and_sizes_window(self):
        outline = gtk_ui.WindowOutline()
        try:
            outline.show_around(Rect(30, 40, 500, 400))
            assert outline.get_visible()
            assert outline.get_size() == (500, 400)
            assert outline.get_position() == (30, 40)
            assert outline.get_accept_focus() is False
            outline.hide()
            assert not outline.get_visible()
        finally:
            outline.destroy()

    def test_degenerate_rect_stays_hidden(self):
        outline = gtk_ui.WindowOutline()
        try:
            outline.show_around(Rect(0, 0, 0, 10))
            assert not outline.get_visible()
        finally:
            outline.destroy()
