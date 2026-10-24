"""Unit tests for landmark image processing and caching."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.config import ConfigManager
from core.landmark import (
    get_cache_key,
    get_default_landmark_path,
    get_landmark_for_location,
    process_landmark_image,
    resolve_landmark_image,
    set_landmark_for_location,
)


class TestLandmark(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_img_path = Path(self.temp_dir.name) / "raw_landmark.jpg"
        # Create a sample 800x600 test image with colors
        img = Image.new("RGB", (800, 600), color=(120, 180, 220))
        img.save(self.test_img_path, "JPEG")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_process_valid_image(self):
        out_path = Path(self.temp_dir.name) / "processed.png"
        res = process_landmark_image(
            source_path=self.test_img_path,
            target_w=460,
            target_h=280,
            dimming=0.35,
            blur_radius=4.0,
            is_light=True,
            output_path=out_path,
        )
        self.assertIsNotNone(res)
        self.assertTrue(out_path.is_file())

        # Verify dimensions of output
        with Image.open(out_path) as out_img:
            self.assertEqual(out_img.size, (460, 280))
            self.assertEqual(out_img.mode, "RGBA")

    def test_missing_image_returns_none(self):
        fake_path = Path(self.temp_dir.name) / "does_not_exist.jpg"
        res = process_landmark_image(
            source_path=fake_path,
            target_w=400,
            target_h=200,
        )
        self.assertIsNone(res)

    def test_cache_key_deterministic(self):
        k1 = get_cache_key(self.test_img_path, 400, 200, 0.35, 3.0, True)
        k2 = get_cache_key(self.test_img_path, 400, 200, 0.35, 3.0, True)
        self.assertEqual(k1, k2)

        # Different parameters yield different keys
        k3 = get_cache_key(self.test_img_path, 400, 200, 0.50, 3.0, True)
        self.assertNotEqual(k1, k3)

    def test_default_landmark_path_exists(self):
        def_path = get_default_landmark_path()
        self.assertTrue(def_path.is_file(), f"Default landmark not found at {def_path}")

    def test_location_binding_and_resolution(self):
        cfg = ConfigManager(Path(self.temp_dir.name) / "test_config.json")
        # Create two test city images
        moscow_img = Path(self.temp_dir.name) / "moscow.jpg"
        spb_img = Path(self.temp_dir.name) / "spb.jpg"
        Image.new("RGB", (200, 200), (200, 50, 50)).save(moscow_img, "JPEG")
        Image.new("RGB", (200, 200), (50, 50, 200)).save(spb_img, "JPEG")

        # Initially no location set -> resolves to built-in default
        res_empty = resolve_landmark_image(cfg, "Москва")
        self.assertEqual(res_empty, get_default_landmark_path())

        # Bind image to Москва
        set_landmark_for_location(cfg, "Москва", str(moscow_img))
        self.assertEqual(get_landmark_for_location(cfg, "Москва"), str(moscow_img))
        self.assertEqual(resolve_landmark_image(cfg, "Москва"), moscow_img)

        # Санкт-Петербург has no binding -> falls back to default
        self.assertEqual(resolve_landmark_image(cfg, "Санкт-Петербург"), get_default_landmark_path())

        # Bind Санкт-Петербург
        set_landmark_for_location(cfg, "Санкт-Петербург", str(spb_img))
        self.assertEqual(resolve_landmark_image(cfg, "Санкт-Петербург"), spb_img)

        # Clearing location reverts to default
        set_landmark_for_location(cfg, "Москва", "")
        self.assertEqual(resolve_landmark_image(cfg, "Москва"), get_default_landmark_path())


if __name__ == "__main__":
    unittest.main()
