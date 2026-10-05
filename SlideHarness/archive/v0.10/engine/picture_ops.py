from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image
from pptx.enum.shapes import MSO_SHAPE_TYPE


def _coerce_focal_point(value: Any) -> tuple[float, float]:
    try:
        return (
            max(0.0, min(1.0, float(value[0]))),
            max(0.0, min(1.0, float(value[1]))),
        )
    except Exception:
        return 0.5, 0.5


def move_shape_to_box(shape, box) -> None:
    """Move/resize a PowerPoint shape to a Box-like object in inches."""
    from pptx.util import Inches

    shape.left = Inches(float(box.x))
    shape.top = Inches(float(box.y))
    shape.width = Inches(float(box.w))
    shape.height = Inches(float(box.h))


def move_shape_to_back(shape) -> None:
    """Place an existing shape behind slide content while preserving the shape itself."""
    element = shape.element
    parent = element.getparent()
    if parent is None:
        return
    parent.remove(element)
    # p:spTree starts with nvGrpSpPr and grpSpPr. Index 2 is the first drawable slot.
    parent.insert(min(2, len(parent)), element)


def move_shape_before(shape, before_shape) -> None:
    element = shape.element
    before = before_shape.element
    parent = element.getparent()
    if parent is None or before.getparent() is not parent:
        return
    parent.remove(element)
    parent.insert(parent.index(before), element)


def replace_picture(
    slide,
    old_shape,
    image_path: str | Path,
    *,
    fit_mode: str = "contain",
    focal_point: Any = None,
    target_box: Any = None,
):
    """Replace a picture without distorting it.

    `preserve_format` swaps only the image relationship and preserves the existing
    PowerPoint picture element, shape id, z-order, mask, outline, effect and rotation.
    `cover` does the same and computes crop fractions for the current/target geometry.
    `contain` is a conservative fallback that may replace the picture with a centered
    new picture shape.
    """
    if old_shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
        raise ValueError(f"Shape {old_shape.shape_id} is not a picture")

    image_path = Path(image_path)
    with Image.open(image_path) as im:
        iw, ih = im.size
    if iw <= 0 or ih <= 0:
        raise ValueError("invalid image size")

    if target_box is not None:
        move_shape_to_box(old_shape, target_box)

    left, top, tw, th = old_shape.left, old_shape.top, old_shape.width, old_shape.height
    target_ar = float(tw) / max(1.0, float(th))
    image_ar = float(iw) / float(ih)
    fit_mode = str(fit_mode or "contain").lower()
    fx, fy = _coerce_focal_point(focal_point)

    if fit_mode in {"cover", "preserve_format"}:
        _image_part, r_id = slide.part.get_or_add_image_part(str(image_path))
        old_shape._pic.blipFill.blip.rEmbed = r_id
        # `preserve_format` is a literal relationship swap. Existing crop, mask,
        # outline, effects, z-order and rotation remain untouched. This is the
        # safest operation for a source Picture that already acts as a designed
        # visual component.
        if fit_mode == "preserve_format":
            return old_shape
        old_shape.crop_left = old_shape.crop_right = 0.0
        old_shape.crop_top = old_shape.crop_bottom = 0.0
        if image_ar > target_ar:
            visible = max(0.001, min(1.0, target_ar / image_ar))
            start = max(0.0, min(1.0 - visible, fx - visible / 2))
            old_shape.crop_left = start
            old_shape.crop_right = max(0.0, 1.0 - (start + visible))
        elif image_ar < target_ar:
            visible = max(0.001, min(1.0, image_ar / target_ar))
            start = max(0.0, min(1.0 - visible, fy - visible / 2))
            old_shape.crop_top = start
            old_shape.crop_bottom = max(0.0, 1.0 - (start + visible))
        return old_shape

    if fit_mode != "contain":
        raise ValueError(f"unsupported picture fit mode: {fit_mode}")

    if image_ar >= target_ar:
        nw = tw
        nh = int(tw / image_ar)
        nl = left
        nt = top + (th - nh) // 2
    else:
        nh = th
        nw = int(th * image_ar)
        nt = top
        nl = left + (tw - nw) // 2
    pic = slide.shapes.add_picture(str(image_path), nl, nt, width=nw, height=nh)
    try:
        pic.rotation = old_shape.rotation
    except Exception:
        pass
    old_el = old_shape.element
    pic_el = pic.element
    parent = old_el.getparent()
    parent.remove(pic_el)
    old_index = parent.index(old_el)
    parent.insert(old_index, pic_el)
    parent.remove(old_el)
    return pic
