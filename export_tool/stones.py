"""Stone position classification and aggregation -- ported from the source
HTML tool's cert-based position rule (the one part of "Stone Position
Rules" that's actually live; a keyword-table settings panel next to it in
the source tool was dead code, never consulted anywhere, and isn't ported --
source-tool problem 1) and aggStones' cert/shape grouping."""
from export_tool import config
from export_tool._util import is_blank


def classify_position(cert, pcs) -> str:
    if not is_blank(cert):
        return "center"
    if pcs is None or pcs <= 1:
        return "center"
    return "side"


def aggregate(stones: list) -> list:
    center_by_cert = {}
    center_no_cert = []
    side_by_shape = {}

    for stone in stones:
        if stone["position"] == "center":
            cert = stone["cert"]
            if cert:
                if cert not in center_by_cert:
                    center_by_cert[cert] = dict(stone, cts=stone["cts"] or 0, pcs=stone["pcs"] or 0, val=stone["val"] or 0)
                else:
                    group = center_by_cert[cert]
                    group["cts"] += stone["cts"] or 0
                    group["pcs"] += stone["pcs"] or 0
                    group["val"] += stone["val"] or 0
            else:
                center_no_cert.append(dict(stone))
        else:
            shape = (stone["shape"] or "").strip().upper() or "UNKNOWN"
            if shape not in side_by_shape:
                side_by_shape[shape] = dict(stone, cts=stone["cts"] or 0, pcs=stone["pcs"] or 0, val=stone["val"] or 0)
            else:
                group = side_by_shape[shape]
                group["cts"] += stone["cts"] or 0
                group["pcs"] += stone["pcs"] or 0
                group["val"] += stone["val"] or 0
                if group["color"] != stone["color"]:
                    group["color"] = None
                if group["clarity"] != stone["clarity"]:
                    group["clarity"] = None

    groups = list(center_by_cert.values()) + center_no_cert + list(side_by_shape.values())

    if config.SINGLE_CENTER_PROMOTION and groups and all(g["position"] != "center" for g in groups):
        groups[0]["position"] = "center"

    return groups
