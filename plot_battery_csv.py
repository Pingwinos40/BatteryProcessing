#!/usr/bin/env python3
"""
plot_battery_csv.py
───────────────────
Interactive plotting utility for processed battery cycler CSV files.
Provides a CLI menu to select X and Y columns, optional color-by-status,
and optional cycle filtering.

Usage:
    python plot_battery_csv.py <processed.csv>

Dependencies:
    pip install pandas matplotlib

Design notes (for future extension):
  - Could add --gui flag to launch a Tkinter/Qt column picker
  - Could add --batch mode to generate a set of standard plots automatically
  - Subsampling is offered for large datasets (>100k rows) to keep plotting
    responsive; the user can override this.
"""

import argparse
import sys
import os

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

# Use a non-interactive backend if no display; switch to TkAgg if available
try:
    matplotlib.use("TkAgg")
except Exception:
    matplotlib.use("Agg")


# Standard battery-relevant plot presets
PRESETS = {
    "voltage_vs_time":      ("relative_time_s", "voltage_mV",   "Voltage vs Time"),
    "current_vs_time":      ("relative_time_s", "current_mA",   "Current vs Time"),
    "capacity_vs_time":     ("relative_time_s", "capacity_mAh", "Capacity vs Time"),
    "voltage_vs_capacity":  ("capacity_mAh",    "voltage_mV",   "Voltage vs Capacity"),
}

STATUS_COLORS = {
    "CC_charge":    "#1f77b4",  # blue
    "CC_discharge": "#d62728",  # red
    "CV_charge":    "#2ca02c",  # green
    "CV_discharge": "#ff7f0e",  # orange
    "rest":         "#7f7f7f",  # gray
}


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "absolute_time" in df.columns:
        df["absolute_time"] = pd.to_datetime(df["absolute_time"], errors="coerce")
    return df


def list_columns(df: pd.DataFrame) -> None:
    print("\nAvailable columns:")
    for i, col in enumerate(df.columns):
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        print(f"  [{i}] {col:25s}  ({dtype}, {non_null:,} non-null)")


def pick_column(df: pd.DataFrame, prompt: str) -> str:
    """Let user pick a column by index or name."""
    while True:
        choice = input(prompt).strip()
        if choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(df.columns):
                return df.columns[idx]
        elif choice in df.columns:
            return choice
        print(f"  Invalid. Enter a column index (0-{len(df.columns)-1}) or name.")


def subsample_if_needed(df: pd.DataFrame, max_points: int = 100_000) -> pd.DataFrame:
    """Subsample large DataFrames for responsive plotting."""
    if len(df) <= max_points:
        return df
    step = len(df) // max_points
    print(f"  (Subsampling {len(df):,} → {len(df)//step:,} points for plotting)")
    return df.iloc[::step]


def do_plot(df: pd.DataFrame, x_col: str, y_col: str,
            color_by_status: bool = False, title: str = "",
            save_path: str | None = None) -> None:
    """Create a scatter/line plot."""
    fig, ax = plt.subplots(figsize=(12, 6))

    plot_df = subsample_if_needed(df)

    if color_by_status and "status" in plot_df.columns:
        for status, group in plot_df.groupby("status"):
            color = STATUS_COLORS.get(status, "#333333")
            ax.scatter(group[x_col], group[y_col], s=1, alpha=0.5,
                       color=color, label=status)
        ax.legend(markerscale=8, loc="best")
    else:
        ax.scatter(plot_df[x_col], plot_df[y_col], s=1, alpha=0.3, color="#1f77b4")

    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(title or f"{y_col} vs {x_col}")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
        print(f"  Saved: {save_path}")
    else:
        plt.show()

    plt.close(fig)


def plot_per_cycle(df: pd.DataFrame, output_dir: str = "cycle_plots") -> None:
    """
    Generate two plots per reported cycle:
      1. Cycle-relative time (s) vs Voltage (mV)  — colored by status
      2. Capacity (mAh) vs Voltage (mV)            — colored by status

    Time is zeroed to the start of each cycle so the x-axis always begins at 0.
    Plots are saved as PNGs into output_dir/.
    """
    os.makedirs(output_dir, exist_ok=True)

    if "cycle" not in df.columns:
        print("Error: no 'cycle' column found in data.")
        return

    cycles = sorted(df["cycle"].unique())
    print(f"\nGenerating per-cycle plots for {len(cycles)} cycles → {output_dir}/")

    for cyc in cycles:
        cyc_df = df[df["cycle"] == cyc].copy()
        if cyc_df.empty:
            continue

        # Zero the time axis to the start of this cycle
        t0 = cyc_df["relative_time_s"].min()
        cyc_df["cycle_time_s"] = cyc_df["relative_time_s"] - t0

        # ── Plot 1: Cycle-relative time vs Voltage ───────────────────────
        fig, ax = plt.subplots(figsize=(10, 5))
        for status, group in cyc_df.groupby("status"):
            color = STATUS_COLORS.get(status, "#333333")
            ax.plot(group["cycle_time_s"], group["voltage_mV"],
                    linewidth=0.6, alpha=0.8, color=color, label=status)
        ax.set_xlabel("Time from cycle start (s)")
        ax.set_ylabel("Voltage (mV)")
        ax.set_title(f"Cycle {cyc} — Voltage vs Time")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path1 = os.path.join(output_dir, f"cycle_{cyc:03d}_voltage_vs_time.png")
        fig.savefig(path1, dpi=150)
        plt.close(fig)

        # ── Plot 2: Capacity vs Voltage ──────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 5))
        for status, group in cyc_df.groupby("status"):
            color = STATUS_COLORS.get(status, "#333333")
            ax.plot(group["capacity_mAh"], group["voltage_mV"],
                    linewidth=0.6, alpha=0.8, color=color, label=status)
        ax.set_xlabel("Capacity (mAh)")
        ax.set_ylabel("Voltage (mV)")
        ax.set_title(f"Cycle {cyc} — Voltage vs Capacity")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path2 = os.path.join(output_dir, f"cycle_{cyc:03d}_voltage_vs_capacity.png")
        fig.savefig(path2, dpi=150)
        plt.close(fig)

        print(f"  Cycle {cyc}: {len(cyc_df):,} pts → {path1}, {path2}")

    print(f"\nDone. {len(cycles) * 2} plots saved to {output_dir}/")


def interactive_menu(df: pd.DataFrame) -> None:
    """Main interactive loop."""
    while True:
        print(f"\n{'─'*50}")
        print("Battery Data Plotter")
        print(f"  Loaded: {len(df):,} rows × {len(df.columns)} cols")
        print(f"{'─'*50}")
        print("\nOptions:")
        print("  [1] Pick X and Y columns manually")
        print("  [2] Use a preset plot")
        print("  [3] Filter by cycle range, then plot")
        print("  [4] Show column summary")
        print("  [5] Generate per-cycle plots (voltage vs time & capacity)")
        print("  [q] Quit")

        choice = input("\n> ").strip().lower()

        if choice == "q":
            break

        elif choice == "1":
            list_columns(df)
            x_col = pick_column(df, "  X column: ")
            y_col = pick_column(df, "  Y column: ")
            color = input("  Color by status? [y/N]: ").strip().lower() == "y"
            save = input("  Save to file? (path or Enter to show): ").strip()
            do_plot(df, x_col, y_col, color_by_status=color,
                    save_path=save or None)

        elif choice == "2":
            print("\nPresets:")
            for key, (x, y, label) in PRESETS.items():
                avail = "✓" if (x in df.columns and y in df.columns) else "✗"
                print(f"  [{key}] {label}  {avail}")
            pkey = input("  Preset name: ").strip()
            if pkey in PRESETS:
                x, y, title = PRESETS[pkey]
                if x in df.columns and y in df.columns:
                    color = input("  Color by status? [y/N]: ").strip().lower() == "y"
                    save = input("  Save to file? (path or Enter to show): ").strip()
                    do_plot(df, x, y, color_by_status=color, title=title,
                            save_path=save or None)
                else:
                    print(f"  Missing column(s) for this preset.")
            else:
                print("  Unknown preset.")

        elif choice == "3":
            if "cycle" not in df.columns:
                print("  No 'cycle' column found.")
                continue
            cycles = sorted(df["cycle"].unique())
            print(f"  Available cycles: {cycles}")
            lo = int(input("  Start cycle: "))
            hi = int(input("  End cycle: "))
            filtered = df[(df["cycle"] >= lo) & (df["cycle"] <= hi)]
            print(f"  Filtered to {len(filtered):,} rows")
            list_columns(filtered)
            x_col = pick_column(filtered, "  X column: ")
            y_col = pick_column(filtered, "  Y column: ")
            color = input("  Color by status? [y/N]: ").strip().lower() == "y"
            save = input("  Save to file? (path or Enter to show): ").strip()
            do_plot(filtered, x_col, y_col, color_by_status=color,
                    title=f"{y_col} vs {x_col} (cycles {lo}–{hi})",
                    save_path=save or None)

        elif choice == "4":
            list_columns(df)

        elif choice == "5":
            out = input("  Output directory [cycle_plots]: ").strip() or "cycle_plots"
            plot_per_cycle(df, output_dir=out)

        else:
            print("  Unknown option.")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive plotter for processed battery cycler CSVs"
    )
    parser.add_argument("csv", help="Path to the processed CSV file")
    parser.add_argument(
        "--preset", choices=list(PRESETS.keys()),
        help="Run a preset plot non-interactively and save as PNG"
    )
    parser.add_argument("--save", help="Output PNG path (with --preset)")
    parser.add_argument("--color-by-status", action="store_true",
                        help="Color points by charge/discharge/rest status")
    parser.add_argument("--per-cycle", action="store_true",
                        help="Generate per-cycle V-vs-time and V-vs-capacity plots")
    parser.add_argument("--cycle-dir", default="cycle_plots",
                        help="Output directory for per-cycle plots (default: cycle_plots)")
    args = parser.parse_args()

    if not os.path.isfile(args.csv):
        print(f"Error: file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    df = load_data(args.csv)
    print(f"Loaded {len(df):,} rows from {args.csv}")

    if args.per_cycle:
        plot_per_cycle(df, output_dir=args.cycle_dir)
        return

    if args.preset:
        x, y, title = PRESETS[args.preset]
        save_path = args.save or f"{args.preset}.png"
        do_plot(df, x, y, color_by_status=args.color_by_status,
                title=title, save_path=save_path)
    else:
        interactive_menu(df)


if __name__ == "__main__":
    main()
