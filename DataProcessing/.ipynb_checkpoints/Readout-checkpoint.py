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
