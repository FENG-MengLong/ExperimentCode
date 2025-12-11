import pandas as pd
import numpy as np
import re
import json


def read_saved_csv(filename):
    """
    Reads your custom CSV file saved by PlotSaver.
    Automatically detects:
      - 1D or 2D format
      - x, y, Z arrays
      - metadata and notes
    Returns:
      x, y, Z, meta_dict
    """

    meta = {}
    header_lines = []

    # --- First read header lines starting with '#' ---
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith("#"):
                header_lines.append(line.strip())
            else:
                break  # stop at first non-header line

    # --- Parse metadata ---
    for line in header_lines:
        m = re.match(r"#\s*([^:]+)\s*:\s*(.*)", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if key == "Notes":
                # parse "a=b; c=d; e=f"
                if val:
                    notes_dict = {}
                    for item in val.split(";"):
                        if "=" in item:
                            k, v = item.split("=", 1)
                            notes_dict[k.strip()] = v.strip()
                    meta["Notes"] = notes_dict
                else:
                    meta["Notes"] = {}
            else:
                meta[key] = val

    # --- Load numeric data (skip header lines) ---
    df = pd.read_csv(filename, comment="#")

    # =============================
    # Case A: 2D data (x,y,z)
    # =============================
    if "y" in df.columns:
        x = np.unique(df["x"].values)
        y = np.unique(df["y"].values)

        # Reconstruct Z with shape (len(x), len(y))
        Z = df.pivot(index="x", columns="y", values="z").values

        return x, y, Z, meta

    # =============================
    # Case B: 1D data (x,z)
    # =============================
    else:
        x = df["x"].values
        Z = df["z"].values
        return x, None, Z, meta


from datetime import datetime
import os
import re

def _normalize_date_to_yyyymmdd(date):
    """
    Accepts:
      - '20251211'
      - '2025-12-11'
      - '2025/12/11'
      - datetime object
    Returns:
      'YYYYMMDD' string.
    """
    if isinstance(date, datetime):
        return date.strftime("%Y%m%d")
    elif isinstance(date, str):
        # keep only digits
        digits = re.sub(r"[^0-9]", "", date)
        if len(digits) != 8:
            raise ValueError(f"Cannot parse date string '{date}' to YYYYMMDD")
        return digits
    else:
        raise TypeError(f"Unsupported date type: {type(date)}")


def build_csv_path(root_dir, date, plot_id):
    """
    Build the CSV path consistent with PlotSaver:
      root_dir / YYYY / MM / DD / YYYYMMDD_ID{plot_id}.csv

    Inputs:
      - root_dir: same as PlotSaver.root_dir
      - date: 'YYYYMMDD', 'YYYY-MM-DD', 'YYYY/MM/DD', or datetime
      - plot_id: integer ID

    Returns:
      - full path to the CSV file (string)
    """
    date_str = _normalize_date_to_yyyymmdd(date)
    year = date_str[0:4]
    month = date_str[4:6]
    day = date_str[6:8]

    filename = f"{date_str}_ID{int(plot_id)}.csv"
    full_path = os.path.join(root_dir, year, month, day, filename)
    return full_path


def read_saved_csv_by_id(root_dir, date, plot_id):
    """
    Convenience wrapper:
    Given root_dir + date + plot_id, follow PlotSaver's folder structure
    and call `read_saved_csv` on the resolved CSV file.

    Returns:
      x, y, Z, meta_dict (same as read_saved_csv)
    """
    csv_path = build_csv_path(root_dir, date, plot_id)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    return read_saved_csv(csv_path)
