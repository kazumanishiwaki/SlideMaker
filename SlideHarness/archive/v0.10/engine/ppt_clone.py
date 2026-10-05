from __future__ import annotations
from copy import deepcopy


def remove_layout_placeholders(slide) -> None:
    for shape in list(slide.shapes):
        el = shape.element
        el.getparent().remove(el)


def clone_slide_into(prs, source_slide):
    """Clone a source slide inside the same pptx package preserving editable shapes/relationships."""
    new_slide = prs.slides.add_slide(source_slide.slide_layout)
    remove_layout_placeholders(new_slide)

    # Slide backgrounds live outside the shape tree. Copy them explicitly or a dark/source
    # slide can turn white even though every shape was cloned correctly.
    src_bg = source_slide.element.cSld.bg
    dst_bg = new_slide.element.cSld.bg
    if dst_bg is not None:
        new_slide.element.cSld.remove(dst_bg)
    if src_bg is not None:
        new_slide.element.cSld.insert(0, deepcopy(src_bg))

    # Preserve a slide-specific color-map override when present.
    src_clr = source_slide.element.clrMapOvr
    dst_clr = new_slide.element.clrMapOvr
    if dst_clr is not None:
        new_slide.element.remove(dst_clr)
    if src_clr is not None:
        new_slide.element.append(deepcopy(src_clr))

    rel_map: dict[str, str] = {}
    for rel in source_slide.part.rels.values():
        if rel.reltype.endswith('/slideLayout') or rel.reltype.endswith('/notesSlide'):
            continue
        target = rel.target_ref if rel.is_external else rel.target_part
        new_rid = new_slide.part.rels._add_relationship(rel.reltype, target, is_external=rel.is_external)
        rel_map[rel.rId] = new_rid
    for shape in source_slide.shapes:
        element = deepcopy(shape.element)
        for node in element.iter():
            for attr, value in list(node.attrib.items()):
                if value in rel_map:
                    node.attrib[attr] = rel_map[value]
        new_slide.shapes._spTree.insert_element_before(element, 'p:extLst')
    return new_slide
