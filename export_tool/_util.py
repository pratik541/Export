"""Small shared helpers used across the export_tool package -- ported from
the source HTML tool's isBlank/safeNum/masterStyle, which every parsing and
building module there relied on."""


def is_blank(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() == "nan"


def safe_num(value):
    if is_blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def master_style(style_no):
    if not style_no:
        return style_no
    return str(style_no).split("/")[0]
