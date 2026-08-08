"""Parses the Jobsheet (OMS CSV export) into an index keyed by every
identifying column a row has a value for -- Order Id, Setting SKU, StyleNo,
Style No. -- so a packing-list item can be looked up by whichever of those
matches its style number. Ported from the source HTML tool's jsIdx
construction (a hand-rolled CSV parser there; pandas.read_csv here, already
a project dependency)."""
from io import BytesIO

import pandas as pd

from export_tool import config


def parse_jobsheet(file_bytes: bytes) -> dict:
    frame = pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False)
    index = {}
    for _, row in frame.iterrows():
        record = row.to_dict()
        for key_column in config.JOBSHEET_KEY_COLUMNS:
            if key_column not in record:
                continue
            key = record[key_column].strip()
            if key and key not in index:
                index[key] = record
    return index
