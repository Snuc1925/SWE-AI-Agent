from __future__ import annotations

import xml.etree.ElementTree as ET


def skill_to_xml(metadata: dict, instruction: str) -> str:
    root = ET.Element("skill")
    meta = ET.SubElement(root, "metadata")
    for key, value in metadata.items():
        field = ET.SubElement(meta, key)
        field.text = str(value)
    instruction_el = ET.SubElement(root, "instruction")
    instruction_el.text = instruction
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
