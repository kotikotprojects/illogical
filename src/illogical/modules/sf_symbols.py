from __future__ import annotations

from AppKit import (
    NSColor,  # type: ignore[attr-defined]
    NSFontWeightBold,  # type: ignore[attr-defined]
    NSFontWeightRegular,  # type: ignore[attr-defined]
    NSGraphicsContext,  # type: ignore[attr-defined]
    NSImage,  # type: ignore[attr-defined]
    NSImageSymbolConfiguration,  # type: ignore[attr-defined]
    NSImageSymbolScaleMedium,  # type: ignore[attr-defined]
)
from PySide6.QtGui import QIcon, QImage, QPixmap
from Quartz import (
    CGBitmapContextCreate,  # type: ignore[attr-defined]
    CGBitmapContextCreateImage,  # type: ignore[attr-defined]
    CGColorSpaceCreateDeviceRGB,  # type: ignore[attr-defined]
    CGDataProviderCopyData,  # type: ignore[attr-defined]
    CGImageGetDataProvider,  # type: ignore[attr-defined]
    CGImageGetHeight,  # type: ignore[attr-defined]
    CGImageGetWidth,  # type: ignore[attr-defined]
    kCGImageAlphaPremultipliedLast,  # type: ignore[attr-defined]
)

_icon_cache: dict[tuple[str, int, tuple[float, ...] | None, bool], QIcon] = {}

SCALE_FACTOR = 2

DEFAULT_COLOR = (155.0 / 255.0, 153.0 / 255.0, 158.0 / 255.0, 1.0)


def sf_symbol(
    name: str,
    size: int = 16,
    color: tuple[float, float, float, float] | None = None,
    *,
    bold: bool = False,
) -> QIcon:
    color_key = color if color else None
    cache_key = (name, size, color_key, bold)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    ns_image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if ns_image is None:
        return QIcon()

    weight = NSFontWeightBold if bold else NSFontWeightRegular
    size_config = NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
        float(size), weight, NSImageSymbolScaleMedium
    )
    r, g, b, a = color if color else DEFAULT_COLOR
    icon_color = NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, a)
    color_config = NSImageSymbolConfiguration.configurationWithHierarchicalColor_(
        icon_color
    )
    config = size_config.configurationByApplyingConfiguration_(color_config)
    ns_image = ns_image.imageWithSymbolConfiguration_(config)

    img_size = ns_image.size()
    pixel_width = int(img_size.width * SCALE_FACTOR)
    pixel_height = int(img_size.height * SCALE_FACTOR)

    color_space = CGColorSpaceCreateDeviceRGB()
    ctx = CGBitmapContextCreate(
        None,
        pixel_width,
        pixel_height,
        8,
        pixel_width * 4,
        color_space,
        kCGImageAlphaPremultipliedLast,
    )

    NSGraphicsContext.saveGraphicsState()
    ns_ctx = NSGraphicsContext.graphicsContextWithCGContext_flipped_(ctx, False)  # noqa: FBT003
    NSGraphicsContext.setCurrentContext_(ns_ctx)

    ns_image.drawInRect_(((0, 0), (pixel_width, pixel_height)))

    NSGraphicsContext.restoreGraphicsState()

    cg_image = CGBitmapContextCreateImage(ctx)
    if cg_image is None:
        return QIcon()

    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    data_provider = CGImageGetDataProvider(cg_image)
    cf_data = CGDataProviderCopyData(data_provider)

    qimage = QImage(
        bytes(cf_data), width, height, QImage.Format.Format_RGBA8888_Premultiplied
    ).copy()
    qimage.setDevicePixelRatio(SCALE_FACTOR)

    pixmap = QPixmap.fromImage(qimage)
    icon = QIcon(pixmap)
    _icon_cache[cache_key] = icon
    return icon
