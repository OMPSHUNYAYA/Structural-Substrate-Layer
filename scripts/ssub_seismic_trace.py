import pandas as pd
import argparse

def build_seismic_trace(in_csv, out_csv, mag_col="mag", time_col=None, discharge_threshold=5.5):
    df = pd.read_csv(in_csv)

    if mag_col not in df.columns:
        raise ValueError("Magnitude column not found")

    df = df.copy()

    # Ordered observation index
    df["t_s"] = range(len(df))

    # Magnitude proxy
    df["E_proxy"] = df[mag_col].astype(float)

    # Discharge flag (large event trigger)
    df["discharge"] = (df["E_proxy"] >= discharge_threshold).astype(int)

    out = df[["t_s", "E_proxy", "discharge"]]
    out.to_csv(out_csv, index=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_csv", required=True)
    parser.add_argument("--out_csv", required=True)
    parser.add_argument("--mag_col", default="mag")
    parser.add_argument("--discharge_threshold", type=float, default=5.5)

    args = parser.parse_args()

    build_seismic_trace(
        args.in_csv,
        args.out_csv,
        mag_col=args.mag_col,
        discharge_threshold=args.discharge_threshold
    )

    print("Seismic trace prepared:", args.out_csv)
