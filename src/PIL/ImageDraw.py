#
# The Python Imaging Library
# $Id$
#
# drawing interface operations
#
# History:
# 1996-04-13 fl   Created (experimental)
# 1996-08-07 fl   Filled polygons, ellipses.
# 1996-08-13 fl   Added text support
# 1998-06-28 fl   Handle I and F images
# 1998-12-29 fl   Added arc; use arc primitive to draw ellipses
# 1999-01-10 fl   Added shape stuff (experimental)
# 1999-02-06 fl   Added bitmap support
# 1999-02-11 fl   Changed all primitives to take options
# 1999-02-20 fl   Fixed backwards compatibility
# 2000-10-12 fl   Copy on write, when necessary
# 2001-02-18 fl   Use default ink for bitmap/text also in fill mode
# 2002-10-24 fl   Added support for CSS-style color strings
# 2002-12-10 fl   Added experimental support for RGBA-on-RGB drawing
# 2002-12-11 fl   Refactored low-level drawing API (work in progress)
# 2004-08-26 fl   Made Draw() a factory function, added getdraw() support
# 2004-09-04 fl   Added width support to line primitive
# 2004-09-10 fl   Added font mode handling
# 2006-06-19 fl   Added font bearing support (getmask2)
#
# Copyright (c) 1997-2006 by Secret Labs AB
# Copyright (c) 1996-2006 by Fredrik Lundh
#
# See the README file for information on usage and redistribution.
#
from __future__ import annotations

import math
import numbers
import struct
from typing import TYPE_CHECKING, AnyStr, Sequence, cast

from . import Image, ImageColor
from ._deprecate import deprecate
from ._typing import Coords

"""
A simple 2D drawing interface for PIL images.
<p>
Application code should use the <b>Draw</b> factory, instead of
directly.
"""


class ImageDraw:
    font = None

    def __init__(self, im: Image.Image, mode: str | None = None) -> None:
        """
        Create a drawing instance.

        :param im: The image to draw in.
        :param mode: Optional mode to use for color values.  For RGB
           images, this argument can be RGB or RGBA (to blend the
           drawing into the image).  For all other modes, this argument
           must be the same as the image mode.  If omitted, the mode
           defaults to the mode of the image.
        """
        im.load()
        if im.readonly:
            im._copy()  # make it writeable
        blend = 0
        if mode is None:
            mode = im.mode
        if mode != im.mode:
            if mode == "RGBA" and im.mode == "RGB":
                blend = 1
            else:
                msg = "mode mismatch"
                raise ValueError(msg)
        if mode == "P":
            self.palette = im.palette
        else:
            self.palette = None
        self._image = im
        self.im = im.im
        self.draw = Image.core.draw(self.im, blend)
        self.mode = mode
        if mode in ("I", "F"):
            self.ink = self.draw.draw_ink(1)
        else:
            self.ink = self.draw.draw_ink(-1)
        if mode in ("1", "P", "I", "F"):
            # FIXME: fix Fill2 to properly support matte for I+F images
            self.fontmode = "1"
        else:
            self.fontmode = "L"  # aliasing is okay for other modes
        self.fill = False

    if TYPE_CHECKING:
        from . import ImageFont

    def getfont(
        self,
    ) -> ImageFont.ImageFont | ImageFont.FreeTypeFont | ImageFont.TransposedFont:
        """
        Get the current default font.

        To set the default font for this ImageDraw instance::

            from PIL import ImageDraw, ImageFont
            draw.font = ImageFont.truetype("Tests/fonts/FreeMono.ttf")

        To set the default font for all future ImageDraw instances::

            from PIL import ImageDraw, ImageFont
            ImageDraw.ImageDraw.font = ImageFont.truetype("Tests/fonts/FreeMono.ttf")

        If the current default font is ``None``,
        it is initialized with ``ImageFont.load_default()``.

        :returns: An image font."""
        if not self.font:
            # FIXME: should add a font repository
            from . import ImageFont

            self.font = ImageFont.load_default()
        return self.font

    def _getfont(
        self, font_size: float | None
    ) -> ImageFont.ImageFont | ImageFont.FreeTypeFont | ImageFont.TransposedFont:
        if font_size is not None:
            from . import ImageFont

            return ImageFont.load_default(font_size)
        else:
            return self.getfont()

    def _getink(self, ink, fill=None) -> tuple[int | None, int | None]:
        if ink is None and fill is None:
            if self.fill:
                fill = self.ink
            else:
                ink = self.ink
        else:
            if ink is not None:
                if isinstance(ink, str):
                    ink = ImageColor.getcolor(ink, self.mode)
                if self.palette and not isinstance(ink, numbers.Number):
                    ink = self.palette.getcolor(ink, self._image)
                ink = self.draw.draw_ink(ink)
            if fill is not None:
                if isinstance(fill, str):
                    fill = ImageColor.getcolor(fill, self.mode)
                if self.palette and not isinstance(fill, numbers.Number):
                    fill = self.palette.getcolor(fill, self._image)
                fill = self.draw.draw_ink(fill)
        return ink, fill

    def arc(self, xy: Coords, start, end, fill=None, width=1) -> None:
        """Draw an arc."""
        ink, fill = self._getink(fill)
        if ink is not None:
            self.draw.draw_arc(xy, start, end, ink, width)

    def bitmap(self, xy: Sequence[int], bitmap, fill=None) -> None:
        """Draw a bitmap."""
        bitmap.load()
        ink, fill = self._getink(fill)
        if ink is None:
            ink = fill
        if ink is not None:
            self.draw.draw_bitmap(xy, bitmap.im, ink)

    def chord(self, xy: Coords, start, end, fill=None, outline=None, width=1) -> None:
        """Draw a chord."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_chord(xy, start, end, fill, 1)
        if ink is not None and ink != fill and width != 0:
            self.draw.draw_chord(xy, start, end, ink, 0, width)

    def ellipse(self, xy: Coords, fill=None, outline=None, width=1) -> None:
        """Draw an ellipse."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_ellipse(xy, fill, 1)
        if ink is not None and ink != fill and width != 0:
            self.draw.draw_ellipse(xy, ink, 0, width)

    def circle(
        self, xy: Sequence[float], radius: float, fill=None, outline=None, width=1
    ) -> None:
        """Draw a circle given center coordinates and a radius."""
        ellipse_xy = (xy[0] - radius, xy[1] - radius, xy[0] + radius, xy[1] + radius)
        self.ellipse(ellipse_xy, fill, outline, width)

    def line(self, xy: Coords, fill=None, width=0, joint=None) -> None:
        """Draw a line, or a connected sequence of line segments."""
        ink = self._getink(fill)[0]
        if ink is not None:
            self.draw.draw_lines(xy, ink, width)
            if joint == "curve" and width > 4:
                points: Sequence[Sequence[float]]
                if isinstance(xy[0], (list, tuple)):
                    points = cast(Sequence[Sequence[float]], xy)
                else:
                    points = [
                        cast(Sequence[float], tuple(xy[i : i + 2]))
                        for i in range(0, len(xy), 2)
                    ]
                for i in range(1, len(points) - 1):
                    point = points[i]
                    angles = [
                        math.degrees(math.atan2(end[0] - start[0], start[1] - end[1]))
                        % 360
                        for start, end in (
                            (points[i - 1], point),
                            (point, points[i + 1]),
                        )
                    ]
                    if angles[0] == angles[1]:
                        # This is a straight line, so no joint is required
                        continue

                    def coord_at_angle(
                        coord: Sequence[float], angle: float
                    ) -> tuple[float, float]:
                        x, y = coord
                        angle -= 90
                        distance = width / 2 - 1
                        return tuple(
                            p + (math.floor(p_d) if p_d > 0 else math.ceil(p_d))
                            for p, p_d in (
                                (x, distance * math.cos(math.radians(angle))),
                                (y, distance * math.sin(math.radians(angle))),
                            )
                        )

                    flipped = (
                        angles[1] > angles[0] and angles[1] - 180 > angles[0]
                    ) or (angles[1] < angles[0] and angles[1] + 180 > angles[0])
                    coords = [
                        (point[0] - width / 2 + 1, point[1] - width / 2 + 1),
                        (point[0] + width / 2 - 1, point[1] + width / 2 - 1),
                    ]
                    if flipped:
                        start, end = (angles[1] + 90, angles[0] + 90)
                    else:
                        start, end = (angles[0] - 90, angles[1] - 90)
                    self.pieslice(coords, start - 90, end - 90, fill)

                    if width > 8:
                        # Cover potential gaps between the line and the joint
                        if flipped:
                            gap_coords = [
                                coord_at_angle(point, angles[0] + 90),
                                point,
                                coord_at_angle(point, angles[1] + 90),
                            ]
                        else:
                            gap_coords = [
                                coord_at_angle(point, angles[0] - 90),
                                point,
                                coord_at_angle(point, angles[1] - 90),
                            ]
                        self.line(gap_coords, fill, width=3)

    def shape(self, shape, fill=None, outline=None) -> None:
        """(Experimental) Draw a shape."""
        shape.close()
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_outline(shape, fill, 1)
        if ink is not None and ink != fill:
            self.draw.draw_outline(shape, ink, 0)

    def pieslice(
        self, xy: Coords, start, end, fill=None, outline=None, width=1
    ) -> None:
        """Draw a pieslice."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_pieslice(xy, start, end, fill, 1)
        if ink is not None and ink != fill and width != 0:
            self.draw.draw_pieslice(xy, start, end, ink, 0, width)

    def point(self, xy: Coords, fill=None) -> None:
        """Draw one or more individual pixels."""
        ink, fill = self._getink(fill)
        if ink is not None:
            self.draw.draw_points(xy, ink)

    def polygon(self, xy: Coords, fill=None, outline=None, width=1) -> None:
        """Draw a polygon."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_polygon(xy, fill, 1)
        if ink is not None and ink != fill and width != 0:
            if width == 1:
                self.draw.draw_polygon(xy, ink, 0, width)
            elif self.im is not None:
                # To avoid expanding the polygon outwards,
                # use the fill as a mask
                mask = Image.new("1", self.im.size)
                mask_ink = self._getink(1)[0]

                fill_im = mask.copy()
                draw = Draw(fill_im)
                draw.draw.draw_polygon(xy, mask_ink, 1)

                ink_im = mask.copy()
                draw = Draw(ink_im)
                width = width * 2 - 1
                draw.draw.draw_polygon(xy, mask_ink, 0, width)

                mask.paste(ink_im, mask=fill_im)

                im = Image.new(self.mode, self.im.size)
                draw = Draw(im)
                draw.draw.draw_polygon(xy, ink, 0, width)
                self.im.paste(im.im, (0, 0) + im.size, mask.im)

    def regular_polygon(
        self, bounding_circle, n_sides, rotation=0, fill=None, outline=None, width=1
    ) -> None:
        """Draw a regular polygon."""
        xy = _compute_regular_polygon_vertices(bounding_circle, n_sides, rotation)
        self.polygon(xy, fill, outline, width)

    def rectangle(self, xy: Coords, fill=None, outline=None, width=1) -> None:
        """Draw a rectangle."""
        ink, fill = self._getink(outline, fill)
        if fill is not None:
            self.draw.draw_rectangle(xy, fill, 1)
        if ink is not None and ink != fill and width != 0:
            self.draw.draw_rectangle(xy, ink, 0, width)

    def rounded_rectangle(
        self, xy: Coords, radius=0, fill=None, outline=None, width=1, *, corners=None
    ) -> None:
        """Draw a rounded rectangle."""
        if isinstance(xy[0], (list, tuple)):
            (x0, y0), (x1, y1) = cast(Sequence[Sequence[float]], xy)
        else:
            x0, y0, x1, y1 = cast(Sequence[float], xy)
        if x1 < x0:
            msg = "x1 must be greater than or equal to x0"
            raise ValueError(msg)
        if y1 < y0:
            msg = "y1 must be greater than or equal to y0"
            raise ValueError(msg)
        if corners is None:
            corners = (True, True, True, True)

        d = radius * 2

        x0 = round(x0)
        y0 = round(y0)
        x1 = round(x1)
        y1 = round(y1)
        full_x, full_y = False, False
        if all(corners):
            full_x = d >= x1 - x0 - 1
            if full_x:
                # The two left and two right corners are joined
                d = x1 - x0
            full_y = d >= y1 - y0 - 1
            if full_y:
                # The two top and two bottom corners are joined
                d = y1 - y0
            if full_x and full_y:
                # If all corners are joined, that is a circle
                return self.ellipse(xy, fill, outline, width)

        if d == 0 or not any(corners):
            # If the corners have no curve,
            # or there are no corners,
            # that is a rectangle
            return self.rectangle(xy, fill, outline, width)

        r = d // 2
        ink, fill = self._getink(outline, fill)

        def draw_corners(pieslice) -> None:
            parts: tuple[tuple[tuple[float, float, float, float], int, int], ...]
            if full_x:
                # Draw top and bottom halves
                parts = (
                    ((x0, y0, x0 + d, y0 + d), 180, 360),
                    ((x0, y1 - d, x0 + d, y1), 0, 180),
                )
            elif full_y:
                # Draw left and right halves
                parts = (
                    ((x0, y0, x0 + d, y0 + d), 90, 270),
                    ((x1 - d, y0, x1, y0 + d), 270, 90),
                )
            else:
                # Draw four separate corners
                parts = tuple(
                    part
                    for i, part in enumerate(
                        (
                            ((x0, y0, x0 + d, y0 + d), 180, 270),
                            ((x1 - d, y0, x1, y0 + d), 270, 360),
                            ((x1 - d, y1 - d, x1, y1), 0, 90),
                            ((x0, y1 - d, x0 + d, y1), 90, 180),
                        )
                    )
                    if corners[i]
                )
            for part in parts:
                if pieslice:
                    self.draw.draw_pieslice(*(part + (fill, 1)))
                else:
                    self.draw.draw_arc(*(part + (ink, width)))

        if fill is not None:
            draw_corners(True)

            if full_x:
                self.draw.draw_rectangle((x0, y0 + r + 1, x1, y1 - r - 1), fill, 1)
            else:
                self.draw.draw_rectangle((x0 + r + 1, y0, x1 - r - 1, y1), fill, 1)
            if not full_x and not full_y:
                left = [x0, y0, x0 + r, y1]
                if corners[0]:
                    left[1] += r + 1
                if corners[3]:
                    left[3] -= r + 1
                self.draw.draw_rectangle(left, fill, 1)

                right = [x1 - r, y0, x1, y1]
                if corners[1]:
                    right[1] += r + 1
                if corners[2]:
                    right[3] -= r + 1
                self.draw.draw_rectangle(right, fill, 1)
        if ink is not None and ink != fill and width != 0:
            draw_corners(False)

            if not full_x:
                top = [x0, y0, x1, y0 + width - 1]
                if corners[0]:
                    top[0] += r + 1
                if corners[1]:
                    top[2] -= r + 1
                self.draw.draw_rectangle(top, ink, 1)

                bottom = [x0, y1 - width + 1, x1, y1]
                if corners[3]:
                    bottom[0] += r + 1
                if corners[2]:
                    bottom[2] -= r + 1
                self.draw.draw_rectangle(bottom, ink, 1)
            if not full_y:
                left = [x0, y0, x0 + width - 1, y1]
                if corners[0]:
                    left[1] += r + 1
                if corners[3]:
                    left[3] -= r + 1
                self.draw.draw_rectangle(left, ink, 1)

                right = [x1 - width + 1, y0, x1, y1]
                if corners[1]:
                    right[1] += r + 1
                if corners[2]:
                    right[3] -= r + 1
                self.draw.draw_rectangle(right, ink, 1)

    def _multiline_check(self, text: AnyStr) -> bool:
        split_character = "\n" if isinstance(text, str) else b"\n"

        return split_character in text

    def _multiline_split(self, text: AnyStr) -> list[AnyStr]:
        return text.split("\n" if isinstance(text, str) else b"\n")

    def _multiline_spacing(self, font, spacing, stroke_width):
        return (
            self.textbbox((0, 0), "A", font, stroke_width=stroke_width)[3]
            + stroke_width
            + spacing
        )

    def text(
        self,
        xy: tuple[float, float],
        text: str,
        fill=None,
        font: (
            ImageFont.ImageFont
            | ImageFont.FreeTypeFont
            | ImageFont.TransposedFont
            | None
        ) = None,
        anchor=None,
        spacing=4,
        align="left",
        direction=None,
        features=None,
        language=None,
        stroke_width=0,
        stroke_fill=None,
        embedded_color=False,
        *args,
        **kwargs,
    ) -> None:
        """Draw text."""
        if embedded_color and self.mode not in ("RGB", "RGBA"):
            msg = "Embedded color supported only in RGB and RGBA modes"
            raise ValueError(msg)

        if font is None:
            font = self._getfont(kwargs.get("font_size"))

        if self._multiline_check(text):
            return self.multiline_text(
                xy,
                text,
                fill,
                font,
                anchor,
                spacing,
                align,
                direction,
                features,
                language,
                stroke_width,
                stroke_fill,
                embedded_color,
            )

        def getink(fill):
            ink, fill = self._getink(fill)
            if ink is None:
                return fill
            return ink

        def draw_text(ink, stroke_width=0, stroke_offset=None) -> None:
            mode = self.fontmode
            if stroke_width == 0 and embedded_color:
                mode = "RGBA"
            coord = []
            start = []
            for i in range(2):
                coord.append(int(xy[i]))
                start.append(math.modf(xy[i])[0])
            try:
                mask, offset = font.getmask2(  # type: ignore[union-attr,misc]
                    text,
                    mode,
                    direction=direction,
                    features=features,
                    language=language,
                    stroke_width=stroke_width,
                    anchor=anchor,
                    ink=ink,
                    start=start,
                    *args,
                    **kwargs,
                )
                coord = [coord[0] + offset[0], coord[1] + offset[1]]
            except AttributeError:
                try:
                    mask = font.getmask(  # type: ignore[misc]
                        text,
                        mode,
                        direction,
                        features,
                        language,
                        stroke_width,
                        anchor,
                        ink,
                        start=start,
                        *args,
                        **kwargs,
                    )
                except TypeError:
                    mask = font.getmask(text)
            if stroke_offset:
                coord = [coord[0] + stroke_offset[0], coord[1] + stroke_offset[1]]
            if mode == "RGBA":
                # font.getmask2(mode="RGBA") returns color in RGB bands and mask in A
                # extract mask and set text alpha
                color, mask = mask, mask.getband(3)
                ink_alpha = struct.pack("i", ink)[3]
                color.fillband(3, ink_alpha)
                x, y = coord
                if self.im is not None:
                    self.im.paste(
                        color, (x, y, x + mask.size[0], y + mask.size[1]), mask
                    )
            else:
                self.draw.draw_bitmap(coord, mask, ink)

        ink = getink(fill)
        if ink is not None:
            stroke_ink = None
            if stroke_width:
                stroke_ink = getink(stroke_fill) if stroke_fill is not None else ink

            if stroke_ink is not None:
                # Draw stroked text
                draw_text(stroke_ink, stroke_width)

                # Draw normal text
                draw_text(ink, 0)
            else:
                # Only draw normal text
                draw_text(ink)

    def multiline_text(
        self,
        xy: tuple[float, float],
        text: str,
        fill=None,
        font: (
            ImageFont.ImageFont
            | ImageFont.FreeTypeFont
            | ImageFont.TransposedFont
            | None
        ) = None,
        anchor=None,
        spacing=4,
        align="left",
        direction=None,
        features=None,
        language=None,
        stroke_width=0,
        stroke_fill=None,
        embedded_color=False,
        *,
        font_size=None,
    ) -> None:
        if direction == "ttb":
            msg = "ttb direction is unsupported for multiline text"
            raise ValueError(msg)

        if anchor is None:
            anchor = "la"
        elif len(anchor) != 2:
            msg = "anchor must be a 2 character string"
            raise ValueError(msg)
        elif anchor[1] in "tb":
            msg = "anchor not supported for multiline text"
            raise ValueError(msg)

        if font is None:
            font = self._getfont(font_size)

        widths = []
        max_width: float = 0
        lines = self._multiline_split(text)
        line_spacing = self._multiline_spacing(font, spacing, stroke_width)
        for line in lines:
            line_width = self.textlength(
                line, font, direction=direction, features=features, language=language
            )
            widths.append(line_width)
            max_width = max(max_width, line_width)

        top = xy[1]
        if anchor[1] == "m":
            top -= (len(lines) - 1) * line_spacing / 2.0
        elif anchor[1] == "d":
            top -= (len(lines) - 1) * line_spacing

        for idx, line in enumerate(lines):
            left = xy[0]
            width_difference = max_width - widths[idx]

            # first align left by anchor
            if anchor[0] == "m":
                left -= width_difference / 2.0
            elif anchor[0] == "r":
                left -= width_difference

            # then align by align parameter
            if align == "left":
                pass
            elif align == "center":
                left += width_difference / 2.0
            elif align == "right":
                left += width_difference
            else:
                msg = 'align must be "left", "center" or "right"'
                raise ValueError(msg)

            self.text(
                (left, top),
                line,
                fill,
                font,
                anchor,
                direction=direction,
                features=features,
                language=language,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
                embedded_color=embedded_color,
            )
            top += line_spacing

    def textlength(
        self,
        text: str,
        font: (
            ImageFont.ImageFont
            | ImageFont.FreeTypeFont
            | ImageFont.TransposedFont
            | None
        ) = None,
        direction=None,
        features=None,
        language=None,
        embedded_color=False,
        *,
        font_size=None,
    ) -> float:
        """Get the length of a given string, in pixels with 1/64 precision."""
        if self._multiline_check(text):
            msg = "can't measure length of multiline text"
            raise ValueError(msg)
        if embedded_color and self.mode not in ("RGB", "RGBA"):
            msg = "Embedded color supported only in RGB and RGBA modes"
            raise ValueError(msg)

        if font is None:
            font = self._getfont(font_size)
        mode = "RGBA" if embedded_color else self.fontmode
        return font.getlength(text, mode, direction, features, language)

    def textbbox(
        self,
        xy,
        text,
        font=None,
        anchor=None,
        spacing=4,
        align="left",
        direction=None,
        features=None,
        language=None,
        stroke_width=0,
        embedded_color=False,
        *,
        font_size=None,
    ) -> tuple[int, int, int, int]:
        """Get the bounding box of a given string, in pixels."""
        if embedded_color and self.mode not in ("RGB", "RGBA"):
            msg = "Embedded color supported only in RGB and RGBA modes"
            raise ValueError(msg)

        if font is None:
            font = self._getfont(font_size)

        if self._multiline_check(text):
            return self.multiline_textbbox(
                xy,
                text,
                font,
                anchor,
                spacing,
                align,
                direction,
                features,
                language,
                stroke_width,
                embedded_color,
            )

        mode = "RGBA" if embedded_color else self.fontmode
        bbox = font.getbbox(
            text, mode, direction, features, language, stroke_width, anchor
        )
        return bbox[0] + xy[0], bbox[1] + xy[1], bbox[2] + xy[0], bbox[3] + xy[1]

    def multiline_textbbox(
        self,
        xy,
        text,
        font=None,
        anchor=None,
        spacing=4,
        align="left",
        direction=None,
        features=None,
        language=None,
        stroke_width=0,
        embedded_color=False,
        *,
        font_size=None,
    ) -> tuple[int, int, int, int]:
        if direction == "ttb":
            msg = "ttb direction is unsupported for multiline text"
            raise ValueError(msg)

        if anchor is None:
            anchor = "la"
        elif len(anchor) != 2:
            msg = "anchor must be a 2 character string"
            raise ValueError(msg)
        elif anchor[1] in "tb":
            msg = "anchor not supported for multiline text"
            raise ValueError(msg)

        if font is None:
            font = self._getfont(font_size)

        widths = []
        max_width: float = 0
        lines = self._multiline_split(text)
        line_spacing = self._multiline_spacing(font, spacing, stroke_width)
        for line in lines:
            line_width = self.textlength(
                line,
                font,
                direction=direction,
                features=features,
                language=language,
                embedded_color=embedded_color,
            )
            widths.append(line_width)
            max_width = max(max_width, line_width)

        top = xy[1]
        if anchor[1] == "m":
            top -= (len(lines) - 1) * line_spacing / 2.0
        elif anchor[1] == "d":
            top -= (len(lines) - 1) * line_spacing

        bbox: tuple[int, int, int, int] | None = None

        for idx, line in enumerate(lines):
            left = xy[0]
            width_difference = max_width - widths[idx]

            # first align left by anchor
            if anchor[0] == "m":
                left -= width_difference / 2.0
            elif anchor[0] == "r":
                left -= width_difference

            # then align by align parameter
            if align == "left":
                pass
            elif align == "center":
                left += width_difference / 2.0
            elif align == "right":
                left += width_difference
            else:
                msg = 'align must be "left", "center" or "right"'
                raise ValueError(msg)

            bbox_line = self.textbbox(
                (left, top),
                line,
                font,
                anchor,
                direction=direction,
                features=features,
                language=language,
                stroke_width=stroke_width,
                embedded_color=embedded_color,
            )
            if bbox is None:
                bbox = bbox_line
            else:
                bbox = (
                    min(bbox[0], bbox_line[0]),
                    min(bbox[1], bbox_line[1]),
                    max(bbox[2], bbox_line[2]),
                    max(bbox[3], bbox_line[3]),
                )

            top += line_spacing

        if bbox is None:
            return xy[0], xy[1], xy[0], xy[1]
        return bbox


def Draw(im, mode: str | None = None) -> ImageDraw:
    """
    A simple 2D drawing interface for PIL images.

    :param im: The image to draw in.
    :param mode: Optional mode to use for color values.  For RGB
       images, this argument can be RGB or RGBA (to blend the
       drawing into the image).  For all other modes, this argument
       must be the same as the image mode.  If omitted, the mode
       defaults to the mode of the image.
    """
    try:
        return im.getdraw(mode)
    except AttributeError:
        return ImageDraw(im, mode)


# experimental access to the outline API
try:
    Outline = Image.core.outline
except AttributeError:
    Outline = None


def getdraw(im=None, hints=None):
    """
    :param im: The image to draw in.
    :param hints: An optional list of hints. Deprecated.
    :returns: A (drawing context, drawing resource factory) tuple.
    """
    if hints is not None:
        deprecate("'hints' parameter", 12)
    from . import ImageDraw2

    if im:
        im = ImageDraw2.Draw(im)
    return im, ImageDraw2


def floodfill(
    image: Image.Image,
    xy: tuple[int, int],
    value: float | tuple[int, ...],
    border: float | tuple[int, ...] | None = None,
    thresh: float = 0,
) -> None:
    """
    (experimental) Fills a bounded region with a given color.

    :param image: Target image.
    :param xy: Seed position (a 2-item coordinate tuple). See
        :ref:`coordinate-system`.
    :param value: Fill color.
    :param border: Optional border value.  If given, the region consists of
        pixels with a color different from the border color.  If not given,
        the region consists of pixels having the same color as the seed
        pixel.
    :param thresh: Optional threshold value which specifies a maximum
        tolerable difference of a pixel value from the 'background' in
        order for it to be replaced. Useful for filling regions of
        non-homogeneous, but similar, colors.
    """
    # based on an implementation by Eric S. Raymond
    # amended by yo1995 @20180806
    pixel = image.load()
    x, y = xy
    try:
        background = pixel[x, y]
        if _color_diff(value, background) <= thresh:
            return  # seed point already has fill color
        pixel[x, y] = value
    except (ValueError, IndexError):
        return  # seed point outside image
    edge = {(x, y)}
    # use a set to keep record of current and previous edge pixels
    # to reduce memory consumption
    full_edge = set()
    while edge:
        new_edge = set()
        for x, y in edge:  # 4 adjacent method
            for s, t in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                # If already processed, or if a coordinate is negative, skip
                if (s, t) in full_edge or s < 0 or t < 0:
                    continue
                try:
                    p = pixel[s, t]
                except (ValueError, IndexError):
                    pass
                else:
                    full_edge.add((s, t))
                    if border is None:
                        fill = _color_diff(p, background) <= thresh
                    else:
                        fill = p not in (value, border)
                    if fill:
                        pixel[s, t] = value
                        new_edge.add((s, t))
        full_edge = edge  # discard pixels processed
        edge = new_edge


def _compute_regular_polygon_vertices(
    bounding_circle, n_sides, rotation
) -> list[tuple[float, float]]:
    """
    Generate a list of vertices for a 2D regular polygon.

    :param bounding_circle: The bounding circle is a tuple defined
        by a point and radius. The polygon is inscribed in this circle.
        (e.g. ``bounding_circle=(x, y, r)`` or ``((x, y), r)``)
    :param n_sides: Number of sides
        (e.g. ``n_sides=3`` for a triangle, ``6`` for a hexagon)
    :param rotation: Apply an arbitrary rotation to the polygon
        (e.g. ``rotation=90``, applies a 90 degree rotation)
    :return: List of regular polygon vertices
        (e.g. ``[(25, 50), (50, 50), (50, 25), (25, 25)]``)

    How are the vertices computed?
    1. Compute the following variables
        - theta: Angle between the apothem & the nearest polygon vertex
        - side_length: Length of each polygon edge
        - centroid: Center of bounding circle (1st, 2nd elements of bounding_circle)
        - polygon_radius: Polygon radius (last element of bounding_circle)
        - angles: Location of each polygon vertex in polar grid
            (e.g. A square with 0 degree rotation => [225.0, 315.0, 45.0, 135.0])

    2. For each angle in angles, get the polygon vertex at that angle
        The vertex is computed using the equation below.
            X= xcos(φ) + ysin(φ)
            Y= −xsin(φ) + ycos(φ)

        Note:
            φ = angle in degrees
            x = 0
            y = polygon_radius

        The formula above assumes rotation around the origin.
        In our case, we are rotating around the centroid.
        To account for this, we use the formula below
            X = xcos(φ) + ysin(φ) + centroid_x
            Y = −xsin(φ) + ycos(φ) + centroid_y
    """
    # 1. Error Handling
    # 1.1 Check `n_sides` has an appropriate value
    if not isinstance(n_sides, int):
        msg = "n_sides should be an int"
        raise TypeError(msg)
    if n_sides < 3:
        msg = "n_sides should be an int > 2"
        raise ValueError(msg)

    # 1.2 Check `bounding_circle` has an appropriate value
    if not isinstance(bounding_circle, (list, tuple)):
        msg = "bounding_circle should be a sequence"
        raise TypeError(msg)

    if len(bounding_circle) == 3:
        *centroid, polygon_radius = bounding_circle
    elif len(bounding_circle) == 2:
        centroid, polygon_radius = bounding_circle
    else:
        msg = (
            "bounding_circle should contain 2D coordinates "
            "and a radius (e.g. (x, y, r) or ((x, y), r) )"
        )
        raise ValueError(msg)

    if not all(isinstance(i, (int, float)) for i in (*centroid, polygon_radius)):
        msg = "bounding_circle should only contain numeric data"
        raise ValueError(msg)

    if not len(centroid) == 2:
        msg = "bounding_circle centre should contain 2D coordinates (e.g. (x, y))"
        raise ValueError(msg)

    if polygon_radius <= 0:
        msg = "bounding_circle radius should be > 0"
        raise ValueError(msg)

    # 1.3 Check `rotation` has an appropriate value
    if not isinstance(rotation, (int, float)):
        msg = "rotation should be an int or float"
        raise ValueError(msg)

    # 2. Define Helper Functions
    def _apply_rotation(point: list[float], degrees: float) -> tuple[int, int]:
        return (
            round(
                point[0] * math.cos(math.radians(360 - degrees))
                - point[1] * math.sin(math.radians(360 - degrees))
                + centroid[0],
                2,
            ),
            round(
                point[1] * math.cos(math.radians(360 - degrees))
                + point[0] * math.sin(math.radians(360 - degrees))
                + centroid[1],
                2,
            ),
        )

    def _compute_polygon_vertex(angle: float) -> tuple[int, int]:
        start_point = [polygon_radius, 0]
        return _apply_rotation(start_point, angle)

    def _get_angles(n_sides: int, rotation: float) -> list[float]:
        angles = []
        degrees = 360 / n_sides
        # Start with the bottom left polygon vertex
        current_angle = (270 - 0.5 * degrees) + rotation
        for _ in range(0, n_sides):
            angles.append(current_angle)
            current_angle += degrees
            if current_angle > 360:
                current_angle -= 360
        return angles

    # 3. Variable Declarations
    angles = _get_angles(n_sides, rotation)

    # 4. Compute Vertices
    return [_compute_polygon_vertex(angle) for angle in angles]


def _color_diff(
    color1: float | tuple[int, ...], color2: float | tuple[int, ...]
) -> float:
    """
    Uses 1-norm distance to calculate difference between two values.
    """
    first = color1 if isinstance(color1, tuple) else (color1,)
    second = color2 if isinstance(color2, tuple) else (color2,)

    return sum(abs(first[i] - second[i]) for i in range(0, len(second)))
