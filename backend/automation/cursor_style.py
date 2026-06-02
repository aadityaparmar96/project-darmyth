# =============================================================
#  Darmyth — backend/automation/cursor_style.py
#  Generates and applies a glowing ring cursor on Windows
#  Restores original cursor on exit
#  Uses: ctypes (built-in), PIL (Pillow)
# =============================================================

import ctypes
import os
import tempfile
import struct
from pathlib import Path

# Windows API constants
IDC_ARROW    = 32512
SPI_SETCURSORS = 0x0057
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE    = 0x02

user32 = ctypes.windll.user32


# ── Generate glowing ring cursor as .cur file ─────────────────
def _create_glowing_ring_cur(size: int = 32,
                              ring_color: tuple = (0, 220, 255),
                              glow_color: tuple = (0, 100, 180)) -> bytes:
    """
    Creates a .cur file in memory with a glowing cyan ring.
    Returns raw bytes of the .cur file.
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        raise ImportError("Pillow not installed. Run: pip install Pillow")

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2

    # Outer glow — draw multiple transparent rings
    for r in range(size//2, size//2 - 6, -1):
        alpha = int(60 * (1 - (size//2 - r) / 6))
        draw.ellipse(
            [cx-r, cy-r, cx+r, cy+r],
            outline=(*glow_color, alpha),
            width=1
        )

    # Main ring
    ring_r = size // 2 - 4
    draw.ellipse(
        [cx-ring_r, cy-ring_r, cx+ring_r, cy+ring_r],
        outline=(*ring_color, 255),
        width=2
    )

    # Inner bright ring
    inner_r = ring_r - 3
    draw.ellipse(
        [cx-inner_r, cy-inner_r, cx+inner_r, cy+inner_r],
        outline=(255, 255, 255, 180),
        width=1
    )

    # Center dot
    draw.ellipse([cx-2, cy-2, cx+2, cy+2],
                fill=(*ring_color, 255))

    # Apply soft glow blur
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))

    # Convert RGBA → AND mask + XOR mask for .cur format
    pixels = list(img.getdata())

    # Build .cur file manually
    # CUR format: ICONDIR + ICONDIRENTRY + ICONIMAGE (DIB)

    width = height = size

    # AND mask — 1 bit per pixel, 1=transparent (we want full transparency where alpha=0)
    and_mask_row_size = ((width + 31) // 32) * 4
    and_mask = bytearray(and_mask_row_size * height)

    # XOR mask — 32bpp BGRA
    xor_mask = bytearray(width * height * 4)

    for y in range(height):
        # Rows are bottom-up in DIB format
        src_y = height - 1 - y
        for x in range(width):
            idx   = src_y * width + x
            r, g, b, a = pixels[idx]

            # XOR mask (BGRA)
            xor_idx = (y * width + x) * 4
            xor_mask[xor_idx]   = b
            xor_mask[xor_idx+1] = g
            xor_mask[xor_idx+2] = r
            xor_mask[xor_idx+3] = a

            # AND mask
            if a < 128:
                bit_pos  = y * and_mask_row_size * 8 + x
                byte_idx = bit_pos // 8
                bit_idx  = 7 - (bit_pos % 8)
                and_mask[byte_idx] |= (1 << bit_idx)

    # BITMAPINFOHEADER — height doubled for AND+XOR
    bih = struct.pack('<IiiHHIIiiII',
        40,           # biSize
        width,        # biWidth
        height * 2,   # biHeight (doubled for cursor)
        1,            # biPlanes
        32,           # biBitCount
        0,            # biCompression (BI_RGB)
        0,            # biSizeImage
        0, 0,         # biXPelsPerMeter, biYPelsPerMeter
        0, 0          # biClrUsed, biClrImportant
    )

    image_data = bih + bytes(xor_mask) + bytes(and_mask)

    # Hotspot = center
    hotspot_x = width  // 2
    hotspot_y = height // 2

    # ICONDIR
    icondir = struct.pack('<HHH', 0, 2, 1)  # reserved, type=2 (cursor), count=1

    # ICONDIRENTRY
    image_offset = 6 + 16   # icondir + one entry
    icondirentry = struct.pack('<BBBBHHII',
        width,         # bWidth
        height,        # bHeight
        0,             # bColorCount
        0,             # bReserved
        hotspot_x,     # wPlanes (hotspot X for cursors)
        hotspot_y,     # wBitCount (hotspot Y for cursors)
        len(image_data),
        image_offset
    )

    return icondir + icondirentry + image_data


# ── Cursor manager ────────────────────────────────────────────
class CursorManager:
    """
    Applies a glowing ring cursor when Darmyth stylus is active.
    Restores original cursor on exit.
    """

    def __init__(self):
        self._cur_file  = None
        self._cursor_h  = None
        self._applied   = False

    def apply_glowing_ring(self,
                           size: int = 32,
                           color: tuple = (0, 220, 255)) -> bool:
        """
        Generate and apply the glowing ring cursor.
        Returns True if successful.
        """
        try:
            # Generate .cur bytes
            cur_bytes = _create_glowing_ring_cur(size=size, ring_color=color)

            # Save to temp file
            tmp = tempfile.NamedTemporaryFile(
                suffix='.cur', delete=False
            )
            tmp.write(cur_bytes)
            tmp.close()
            self._cur_file = tmp.name

            # Load cursor from file
            LR_LOADFROMFILE = 0x00000010
            IMAGE_CURSOR    = 2

            self._cursor_h = user32.LoadImageW(
                None,
                self._cur_file,
                IMAGE_CURSOR,
                0, 0,
                LR_LOADFROMFILE
            )

            if not self._cursor_h:
                print(f"[cursor_style] LoadImage failed: {ctypes.GetLastError()}")
                return False

            # Set cursor for all standard cursor types
            cursor_ids = [
                32512,  # IDC_ARROW
                32513,  # IDC_IBEAM
                32514,  # IDC_WAIT
                32515,  # IDC_CROSS
                32516,  # IDC_UPARROW
            ]
            for cid in cursor_ids:
                user32.SetSystemCursor(self._cursor_h, cid)

            self._applied = True
            print("[cursor_style] Glowing ring cursor applied.")
            return True

        except Exception as e:
            print(f"[cursor_style] Failed to apply cursor: {e}")
            return False

    def restore(self) -> None:
        """Restore Windows default cursors."""
        if self._applied:
            # SystemParametersInfo with SPI_SETCURSORS restores defaults
            user32.SystemParametersInfoW(
                SPI_SETCURSORS, 0, None,
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
            self._applied = False
            print("[cursor_style] Default cursor restored.")

        # Clean up temp file
        if self._cur_file and os.path.exists(self._cur_file):
            try:
                os.unlink(self._cur_file)
            except Exception:
                pass
            self._cur_file = None

    def __del__(self):
        self.restore()


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    print("Testing glowing ring cursor...")
    print("Cursor will change for 5 seconds then restore.\n")

    manager = CursorManager()
    success = manager.apply_glowing_ring(size=32, color=(0, 220, 255))

    if success:
        print("Cursor changed! Move your mouse around.")
        time.sleep(5)
        manager.restore()
        print("Done — cursor restored.")
    else:
        print("Failed. Make sure Pillow is installed: pip install Pillow")
