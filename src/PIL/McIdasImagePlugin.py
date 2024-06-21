#
# The Python Imaging Library.
# $Id$
#
# Basic McIdas support for PIL
#
# History:
# 1997-05-05 fl  Created (8-bit images only)
# 2009-03-08 fl  Added 16/32-bit support.
#
# Thanks to Richard Jones and Craig Swank for specs and samples.
#
# Copyright (c) Secret Labs AB 1997.
# Copyright (c) Fredrik Lundh 1997.
#
# See the README file for information on usage and redistribution.
#
from __future__ import annotations

import struct

from . import Image, ImageFile


def _accept(prefix: bytes) -> bool:
    return prefix[:8] == b"\x00\x00\x00\x00\x00\x00\x00\x04"


##
# Image plugin for McIdas area images.


class McIdasImageFile(ImageFile.ImageFile):
    branches = {
        "1": False,
        "2": False,
        "3": False,
        "4": False,
        "5": False,
        }

    format = "MCIDAS"
    format_description = "McIdas area file"

    def _open(self) -> None:
        # parse area file directory
        assert self.fp is not None

        s = self.fp.read(256)
        if not _accept(s) or len(s) != 256:
            McIdasImageFile.branches["1"] = True
            msg = "not an McIdas area file"
            raise SyntaxError(msg)

        self.area_descriptor_raw = s
        self.area_descriptor = w = [0] + list(struct.unpack("!64i", s))

        # get mode
        if w[11] == 1:
            McIdasImageFile.branches["2"] = True
            mode = rawmode = "L"
        elif w[11] == 2:
            McIdasImageFile.branches["3"] = True
            # FIXME: add memory map support
            mode = "I"
            rawmode = "I;16B"
        elif w[11] == 4:
            McIdasImageFile.branches["4"] = True
            # FIXME: add memory map support
            mode = "I"
            rawmode = "I;32B"
        else:
            McIdasImageFile.branches["5"] = True
            msg = "unsupported McIdas format"
            raise SyntaxError(msg)

        self._mode = mode
        self._size = w[10], w[9]

        offset = w[34] + w[15]
        stride = w[15] + w[10] * w[11] * w[14]

        self.tile = [("raw", (0, 0) + self.size, offset, (rawmode, stride, 1))]


# --------------------------------------------------------------------
# registry

Image.register_open(McIdasImageFile.format, McIdasImageFile, _accept)

# no default extension

