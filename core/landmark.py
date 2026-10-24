"""Landmark image processing and caching for info-weather.

Handles aspect-ratio crop, Gaussian blur, tone tinting/dimming for readability,
and disk caching.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter

from core.logging import get_logger

logger = get_logger("core.landmark")

# Default cache directory for processed landmark backgrounds
DEFAULT_LANDMARK_CACHE_DIR = Path.home() / ".cache" / "info-weather" / "landmarks"
if os.name == "nt":
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        DEFAULT_LANDMARK_CACHE_DIR = Path(local_app_data) / "info-weather" / "cache" / "landmarks"


# Bundled default daytime landmark background
DEFAULT_LANDMARK_PATH = Path(__file__).resolve().parent.parent / "assets" / "backgrounds" / "default_landmark.jpg"


def get_default_landmark_path() -> Path:
    """Return the absolute path to the bundled default daytime landmark background."""
    return DEFAULT_LANDMARK_PATH


def resolve_landmark_image(config_manager: Any, city_name: str | None = None) -> Path | None:
    """Resolve the appropriate landmark image for the given city or global config.

    Resolution order:
    1. City-specific image from landmark["locations"][city_name].
    2. City-specific image from cities list: city["landmark_image"].
    3. Global landmark["image_path"] from configuration.
    4. Bundled default daytime landmark image.
    """
    if config_manager is None:
        def_path = get_default_landmark_path()
        return def_path if def_path.is_file() else None

    landmark_cfg = config_manager.get("landmark", {})
    if not isinstance(landmark_cfg, dict):
        landmark_cfg = {}

    if not city_name:
        city_name = config_manager.get("current_city", "")

    # 1. Check per-location map in landmark config
    if city_name:
        locations_map = landmark_cfg.get("locations", {})
        if isinstance(locations_map, dict):
            loc_p = locations_map.get(city_name)
            if loc_p and Path(loc_p).is_file():
                return Path(loc_p)

        # 2. Check cities array
        cities = config_manager.get("cities", [])
        if isinstance(cities, list):
            for c in cities:
                if isinstance(c, dict) and c.get("name") == city_name:
                    c_img = c.get("landmark_image")
                    if c_img and Path(c_img).is_file():
                        return Path(c_img)

    # 3. Global image_path
    global_p = landmark_cfg.get("image_path", "")
    if global_p and Path(global_p).is_file():
        return Path(global_p)

    # 4. Built-in default landmark
    default_p = get_default_landmark_path()
    if default_p.is_file():
        return default_p

    return None


def get_landmark_for_location(config_manager: Any, city_name: str) -> str:
    """Return the custom image path assigned to a specific city, or empty string."""
    if not config_manager or not city_name:
        return ""
    landmark_cfg = config_manager.get("landmark", {})
    if isinstance(landmark_cfg, dict):
        locations_map = landmark_cfg.get("locations", {})
        if isinstance(locations_map, dict) and city_name in locations_map:
            return str(locations_map[city_name])
    return ""


def set_landmark_for_location(config_manager: Any, city_name: str, image_path: str) -> None:
    """Assign or clear a custom landmark image path for a specific city."""
    if not config_manager or not city_name:
        return
    landmark_cfg = dict(config_manager.get("landmark", {}))
    locations = dict(landmark_cfg.get("locations", {}))
    if image_path:
        locations[city_name] = str(image_path)
    else:
        locations.pop(city_name, None)
    landmark_cfg["locations"] = locations

    # Also keep image_path in sync if this is the active city
    current_city = config_manager.get("current_city", "")
    if city_name == current_city:
        landmark_cfg["image_path"] = str(image_path)

    config_manager.set("landmark", landmark_cfg)


def get_landmark_cache_dir() -> Path:
    """Ensure and return the directory used to cache processed landmark images."""
    DEFAULT_LANDMARK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_LANDMARK_CACHE_DIR


def get_cache_key(
    source_path: str | Path,
    target_w: int,
    target_h: int,
    dimming: float,
    blur_radius: float,
    is_light: bool,
) -> str:
    """Generate a unique deterministic hash key for a processed landmark image."""
    try:
        mtime = os.path.getmtime(source_path)
    except Exception:
        mtime = 0.0

    key_str = f"{Path(source_path).resolve()}_{mtime}_{target_w}x{target_h}_{dimming:.2f}_{blur_radius:.1f}_{is_light}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]


def process_landmark_image(
    source_path: str | Path,
    target_w: int,
    target_h: int,
    dimming: float = 0.35,
    blur_radius: float = 3.0,
    is_light: bool = True,
    output_path: str | Path | None = None,
) -> Path | None:
    """Process a raw user image into a stylized, contrast-balanced widget background.

    Steps:
    1. Validate source file.
    2. Resize & center-crop (cover) to match (target_w, target_h).
    3. Apply Gaussian blur to prevent busy background details from clashing with text.
    4. Apply contrast-preserving tint overlay (dark overlay for readability).
    5. Save processed image to disk.

    Returns the path to the processed PNG, or None on failure.
    """
    src = Path(source_path)
    if not src.is_file():
        logger.warning("Landmark image not found: %s", src)
        return None

    target_w = max(100, int(target_w))
    target_h = max(60, int(target_h))
    dimming = max(0.0, min(0.85, float(dimming)))
    blur_radius = max(0.0, min(20.0, float(blur_radius)))

    out_file = Path(output_path) if output_path else (get_landmark_cache_dir() / f"landmark_{get_cache_key(src, target_w, target_h, dimming, blur_radius, is_light)}.png")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if out_file.is_file():
        return out_file

    try:
        with Image.open(src) as img:
            img = img.convert("RGBA")
            orig_w, orig_h = img.size

            if orig_w <= 0 or orig_h <= 0:
                logger.warning("Invalid image dimensions: %dx%d", orig_w, orig_h)
                return None

            # 1. Aspect cover calculation (Center crop)
            scale = max(target_w / orig_w, target_h / orig_h)
            new_w = int(round(orig_w * scale))
            new_h = int(round(orig_h * scale))
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            img_cropped = img_resized.crop((left, top, left + target_w, top + target_h))

            # 2. Gaussian Blur (if requested)
            if blur_radius > 0.1:
                img_cropped = img_cropped.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            # 3. Tone Tinting Overlay for readability
            # Create a smooth tint overlay
            overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            if is_light:
                # For light theme:
                # Slight desaturation so vibrant photos don't clash with colored weather icons
                enhancer = ImageEnhance.Color(img_cropped)
                img_cropped = enhancer.enhance(0.85)

                # Cool slate / soft sky tint
                tint_r, tint_g, tint_b = 15, 23, 42
                alpha_top = int(round(dimming * 255 * 0.75))
                alpha_bottom = int(round(dimming * 255 * 1.05))
            else:
                # For dark theme:
                # Deep slate / night tint
                tint_r, tint_g, tint_b = 5, 8, 16
                alpha_top = int(round(min(0.85, dimming + 0.18) * 255))
                alpha_bottom = int(round(min(0.92, dimming + 0.35) * 255))

            # Vertical gradient overlay
            overlay_data = []
            for y in range(target_h):
                factor = y / max(1, target_h - 1)
                a = int(round(alpha_top + factor * (alpha_bottom - alpha_top)))
                a = max(0, min(255, a))
                overlay_data.extend([(tint_r, tint_g, tint_b, a)] * target_w)

            overlay.putdata(overlay_data)

            # Composite
            final_img = Image.alpha_composite(img_cropped, overlay)
            final_img.save(out_file, "PNG", optimize=True)
            logger.info("Processed landmark background cached to %s", out_file)
            return out_file

    except Exception as e:
        logger.error("Failed to process landmark image %s: %s", src, e)
        return None
