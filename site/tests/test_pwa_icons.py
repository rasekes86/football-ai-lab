"""Validate PWA icon generation without paid SDKs or external image libraries."""
import importlib.util
from pathlib import Path
import struct
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"build_pwa_icons.py"
spec=importlib.util.spec_from_file_location("football_pwa_icons",SCRIPT)
icons=importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)


class PwaIconTest(unittest.TestCase):
    def test_icon_dimensions_and_png_signature(self):
        png=icons.build_png(192)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        width,height=struct.unpack(">II",png[16:24])
        self.assertEqual((width,height),(192,192))
        self.assertIn(b"IDAT",png)
        self.assertTrue(png.endswith(b"\x00\x00\x00\x00IEND\xaeB\x60\x82"))

    def test_drawing_is_reproducible_and_valid(self):
        self.assertEqual(icons.sample(256,250),icons.sample(256,250))
        self.assertNotEqual(icons.sample(0,0),icons.sample(256,186))
        with self.assertRaises(ValueError):
            icons.build_png(72)


if __name__=="__main__":
    unittest.main()
