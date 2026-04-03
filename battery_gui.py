#!/usr/bin/env python3
"""
battery_gui.py
──────────────
Tkinter GUI for processing and plotting battery cycler data.

Features:
  1. Load raw .xls/.xlsx files from battery tester
     - Concatenates all "Detail" sheets (skips first Info and last Cycle sheet)
     - Translates Mandarin headers and status labels to English
     - Exports processed CSV
  2. Batch plot all cycles (Voltage vs Time, Voltage vs Capacity) at 300 dpi
  3. Custom single-plot with axis selectors, cycle filter, preview, and save

Dependencies:
    pip install pandas matplotlib openpyxl
    (Tkinter ships with Python, openpyxl is the pandas Excel engine)
"""

import os
import sys
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


# ──────────────────────────────────────────────────────────────────────
# Translation mappings
# ──────────────────────────────────────────────────────────────────────

HEADER_MAP = {
    "状态":        "status",
    "跳转":        "jump",
    "循环":        "cycle",
    "步次":        "step",
    "电流(mA)":    "current_mA",
    "电压(mV)":    "voltage_mV",
    "容量(mAH)":   "capacity_mAh",
    "容量(mAh)":   "capacity_mAh",
    "能量(mWH)":   "energy_mWh",
    "能量(mWh)":   "energy_mWh",
    "相对时间(秒)": "relative_time_s",
    "绝对时间":     "absolute_time",
}

# Status values may arrive as GBK bytes decoded as Latin-1 (garbled) or as proper UTF-8
STATUS_MAP_UTF8 = {
    "恒流充电":   "CC_charge",
    "恒流放电":   "CC_discharge",
    "恒压充电":   "CV_charge",
    "恒压放电":   "CV_discharge",
    "搁置":       "rest",
    "静置":       "rest",
}

# Build a garbled→English map by encoding UTF-8 keys to GBK then decoding as Latin-1
STATUS_MAP_GARBLED = {}
for zh, en in STATUS_MAP_UTF8.items():
    try:
        garbled = zh.encode("gbk").decode("latin-1")
        STATUS_MAP_GARBLED[garbled] = en
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

STATUS_MAP = {**STATUS_MAP_UTF8, **STATUS_MAP_GARBLED}

APP_VERSION = "1.0.0"
APP_DATE = "2026-04-03"

STATUS_COLORS = {
    "CC_charge":    "#1f77b4",
    "CC_discharge": "#d62728",
    "CV_charge":    "#2ca02c",
    "CV_discharge": "#ff7f0e",
    "rest":         "#7f7f7f",
}


# ──────────────────────────────────────────────────────────────────────
# Data loading & processing
# ──────────────────────────────────────────────────────────────────────

def load_and_process(filepath: str) -> pd.DataFrame:
    """
    Load a battery tester .xls/.xlsx file:
      - Skip the first sheet (Info) and last sheet (Cycle summary)
      - Concatenate all middle Detail sheets
      - Translate headers and status labels to English
    Returns a processed DataFrame.
    """
    # Use pandas.read_excel — it handles .xls and .xlsx transparently
    xls = pd.ExcelFile(filepath)
    sheet_names = xls.sheet_names

    if len(sheet_names) < 3:
        xls.close()
        raise ValueError(
            f"Expected at least 3 sheets (Info, Detail(s), Cycle), "
            f"got {len(sheet_names)}: {sheet_names}"
        )

    # Middle sheets = everything except first (Info) and last (Cycle)
    detail_names = sheet_names[1:-1]
    frames = []
    for name in detail_names:
        df_sheet = pd.read_excel(xls, sheet_name=name)
        if not df_sheet.empty:
            frames.append(df_sheet)
    xls.close()

    if not frames:
        raise ValueError("No data found in detail sheets.")

    df = pd.concat(frames, ignore_index=True)

    # Translate column headers
    df.rename(columns=HEADER_MAP, inplace=True)

    # Translate status labels
    if "status" in df.columns:
        df["status"] = df["status"].map(lambda s: STATUS_MAP.get(s, s))

    # Ensure numeric columns are numeric
    numeric_cols = ["current_mA", "voltage_mV", "capacity_mAh",
                    "energy_mWh", "relative_time_s", "cycle", "step", "jump"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse absolute time
    if "absolute_time" in df.columns:
        df["absolute_time"] = pd.to_datetime(df["absolute_time"], errors="coerce")

    # Derived column: voltage in volts
    if "voltage_mV" in df.columns:
        df["voltage_V"] = df["voltage_mV"] / 1000.0

    return df


# ──────────────────────────────────────────────────────────────────────
# Main GUI Application
# ──────────────────────────────────────────────────────────────────────

class BatteryGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Battery Data Processor & Plotter")
        self.geometry("1100x750")
        self.minsize(900, 600)

        self.df: Optional[pd.DataFrame] = None
        self.source_path: Optional[str] = None

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────

    def _build_ui(self):
        # Top bar: load file + status
        top = ttk.Frame(self, padding=5)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Load File…", command=self._load_file).pack(side=tk.LEFT)
        self.lbl_file = ttk.Label(top, text="No file loaded", foreground="gray")
        self.lbl_file.pack(side=tk.LEFT, padx=10)

        ttk.Button(top, text="Export Processed CSV…", command=self._export_csv).pack(side=tk.RIGHT)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._build_batch_tab()
        self._build_custom_tab()

        # Footer with version info
        footer = ttk.Frame(self, padding=(5, 2))
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Separator(self).pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(
            footer,
            text=f"v{APP_VERSION}  ({APP_DATE})",
            foreground="gray",
            font=("TkDefaultFont", 8),
        ).pack(side=tk.RIGHT)

    # ── Load / Export ─────────────────────────────────────────────────

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Select Battery Tester File",
            filetypes=[
                ("Excel files", "*.xls *.xlsx"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return

        fname = os.path.basename(path)

        # Show loading indicator
        self.lbl_file.config(text=f"Loading {fname}…", foreground="blue")
        self.config(cursor="watch")
        self.update_idletasks()

        import threading

        def _do_load():
            try:
                df = load_and_process(path)
                # Schedule UI update back on the main thread
                self.after(0, lambda: self._on_load_success(df, path, fname))
            except Exception as e:
                self.after(0, lambda: self._on_load_error(e))

        threading.Thread(target=_do_load, daemon=True).start()

    def _on_load_success(self, df, path, fname):
        self.df = df
        self.source_path = path
        self.config(cursor="")
        nrows = len(self.df)
        ncols = len(self.df.columns)
        self.lbl_file.config(
            text=f"{fname}  —  {nrows:,} rows × {ncols} cols",
            foreground="black"
        )
        self._populate_custom_tab()
        self._populate_batch_tab()

    def _on_load_error(self, error):
        self.config(cursor="")
        self.lbl_file.config(text="Load failed", foreground="red")
        messagebox.showerror("Load Error", str(error))

    def _export_csv(self):
        if self.df is None:
            messagebox.showwarning("No Data", "Load a file first.")
            return

        default_name = ""
        if self.source_path:
            base = os.path.splitext(os.path.basename(self.source_path))[0]
            default_name = f"{base}_processed.csv"

        path = filedialog.asksaveasfilename(
            title="Save Processed CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        self.df.to_csv(path, index=False)
        messagebox.showinfo("Saved", f"Exported {len(self.df):,} rows to:\n{path}")

    # ── Batch Plot Tab ────────────────────────────────────────────────

    def _build_batch_tab(self):
        self.batch_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.batch_frame, text="Batch Plot")

        # Controls row
        ctrl = ttk.Frame(self.batch_frame)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(ctrl, text="Plot style:").pack(side=tk.LEFT)
        self.batch_style = tk.StringVar(value="line")
        ttk.Radiobutton(ctrl, text="Line", variable=self.batch_style, value="line").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Radiobutton(ctrl, text="Scatter", variable=self.batch_style, value="scatter").pack(side=tk.LEFT, padx=(5, 0))

        ttk.Separator(ctrl, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(ctrl, text="Generate All Cycle Plots", command=self._run_batch_plot).pack(side=tk.LEFT)

        self.batch_status = ttk.Label(ctrl, text="", foreground="gray")
        self.batch_status.pack(side=tk.LEFT, padx=10)

        # Progress bar
        self.batch_progress = ttk.Progressbar(self.batch_frame, mode="determinate")
        self.batch_progress.pack(fill=tk.X, pady=(0, 5))

    def _populate_batch_tab(self):
        if self.df is not None and "cycle" in self.df.columns:
            n_cycles = self.df["cycle"].nunique()
            self.batch_status.config(text=f"{n_cycles} cycles detected")
        else:
            self.batch_status.config(text="No cycle data found")

    def _run_batch_plot(self):
        if self.df is None:
            messagebox.showwarning("No Data", "Load a file first.")
            return
        if "cycle" not in self.df.columns:
            messagebox.showwarning("No Cycles", "No 'cycle' column in data.")
            return

        out_dir = filedialog.askdirectory(title="Select Output Folder for Cycle Plots")
        if not out_dir:
            return

        style = self.batch_style.get()
        cycles = sorted(self.df["cycle"].dropna().unique())
        total = len(cycles) * 2
        self.batch_progress["maximum"] = total
        self.batch_progress["value"] = 0
        count = 0

        for cyc in cycles:
            cyc_df = self.df[self.df["cycle"] == cyc].copy()
            if cyc_df.empty:
                continue

            cyc_int = int(cyc)

            # Zero time to start of cycle
            if "relative_time_s" in cyc_df.columns:
                t0 = cyc_df["relative_time_s"].min()
                cyc_df["cycle_time_s"] = cyc_df["relative_time_s"] - t0

            # ── Plot 1: Voltage vs Time ──────────────────────────────
            if "cycle_time_s" in cyc_df.columns and "voltage_V" in cyc_df.columns:
                fig, ax = plt.subplots(figsize=(10, 5))
                self._plot_by_status(ax, cyc_df, "cycle_time_s", "voltage_V", style)
                ax.set_xlabel("Time from cycle start (s)")
                ax.set_ylabel("Voltage (V)")
                ax.set_title(f"Cycle {cyc_int} — Voltage vs Time")
                ax.legend(loc="best")
                ax.grid(True, alpha=0.3)
                fig.tight_layout()
                fig.savefig(
                    os.path.join(out_dir, f"cycle_{cyc_int:03d}_voltage_vs_time.png"),
                    dpi=300
                )
                plt.close(fig)

            count += 1
            self.batch_progress["value"] = count
            self.update_idletasks()

            # ── Plot 2: Voltage vs Capacity ──────────────────────────
            if "capacity_mAh" in cyc_df.columns and "voltage_V" in cyc_df.columns:
                fig, ax = plt.subplots(figsize=(10, 5))
                self._plot_by_status(ax, cyc_df, "capacity_mAh", "voltage_V", style)
                ax.set_xlabel("Capacity (mAh)")
                ax.set_ylabel("Voltage (V)")
                ax.set_title(f"Cycle {cyc_int} — Voltage vs Capacity")
                ax.legend(loc="best")
                ax.grid(True, alpha=0.3)
                fig.tight_layout()
                fig.savefig(
                    os.path.join(out_dir, f"cycle_{cyc_int:03d}_voltage_vs_capacity.png"),
                    dpi=300
                )
                plt.close(fig)

            count += 1
            self.batch_progress["value"] = count
            self.update_idletasks()

        self.batch_status.config(text=f"Done — {count} plots saved to {out_dir}")
        messagebox.showinfo("Batch Plot Complete", f"Saved {count} plots (300 dpi) to:\n{out_dir}")

    @staticmethod
    def _plot_by_status(ax, df, x_col, y_col, style="line"):
        """Plot data colored by status, skipping rest states."""
        if "status" in df.columns:
            for status, group in df.groupby("status"):
                if status == "rest":
                    continue
                color = STATUS_COLORS.get(status, "#333333")
                if style == "line":
                    ax.plot(group[x_col], group[y_col],
                            linewidth=0.8, alpha=0.8, color=color, label=status)
                else:
                    ax.scatter(group[x_col], group[y_col],
                               s=2, alpha=0.5, color=color, label=status)
        else:
            if style == "line":
                ax.plot(df[x_col], df[y_col], linewidth=0.8, alpha=0.8, color="#1f77b4")
            else:
                ax.scatter(df[x_col], df[y_col], s=2, alpha=0.5, color="#1f77b4")

    # ── Custom Plot Tab ───────────────────────────────────────────────

    def _build_custom_tab(self):
        self.custom_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.custom_frame, text="Custom Plot")

        # Left panel: controls
        left = ttk.LabelFrame(self.custom_frame, text="Plot Settings", padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        # X axis
        ttk.Label(left, text="X Axis:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.custom_x = ttk.Combobox(left, state="readonly", width=22)
        self.custom_x.grid(row=0, column=1, pady=2, padx=5)

        # Y axis
        ttk.Label(left, text="Y Axis:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.custom_y = ttk.Combobox(left, state="readonly", width=22)
        self.custom_y.grid(row=1, column=1, pady=2, padx=5)

        # Plot style
        ttk.Label(left, text="Style:").grid(row=2, column=0, sticky=tk.W, pady=2)
        style_frame = ttk.Frame(left)
        style_frame.grid(row=2, column=1, sticky=tk.W, pady=2)
        self.custom_style = tk.StringVar(value="line")
        ttk.Radiobutton(style_frame, text="Line", variable=self.custom_style, value="line").pack(side=tk.LEFT)
        ttk.Radiobutton(style_frame, text="Scatter", variable=self.custom_style, value="scatter").pack(side=tk.LEFT, padx=(5, 0))

        # Color by status
        self.custom_color_status = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Color by status", variable=self.custom_color_status).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=2
        )

        # Cycle selection
        ttk.Separator(left, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=8)
        ttk.Label(left, text="Cycles:").grid(row=5, column=0, sticky=tk.W, pady=2)

        self.cycle_mode = tk.StringVar(value="all")
        ttk.Radiobutton(left, text="All cycles", variable=self.cycle_mode, value="all",
                         command=self._toggle_cycle_entry).grid(row=5, column=1, sticky=tk.W, pady=2)
        ttk.Radiobutton(left, text="Selected:", variable=self.cycle_mode, value="selected",
                         command=self._toggle_cycle_entry).grid(row=6, column=0, sticky=tk.W, pady=2)

        self.cycle_entry = ttk.Entry(left, width=22)
        self.cycle_entry.grid(row=6, column=1, pady=2, padx=5)
        self.cycle_entry.insert(0, "e.g. 1,2,3 or 1-5")
        self.cycle_entry.config(state="disabled")

        # Buttons
        ttk.Separator(left, orient=tk.HORIZONTAL).grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=8)
        ttk.Button(left, text="Preview Plot", command=self._preview_plot).grid(
            row=8, column=0, columnspan=2, sticky=tk.EW, pady=2
        )
        ttk.Button(left, text="Save as PNG (300 dpi)…", command=self._save_custom_plot).grid(
            row=9, column=0, columnspan=2, sticky=tk.EW, pady=2
        )

        # Right panel: matplotlib canvas
        right = ttk.Frame(self.custom_frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.custom_fig = Figure(figsize=(8, 5), dpi=100)
        self.custom_ax = self.custom_fig.add_subplot(111)
        self.custom_canvas = FigureCanvasTkAgg(self.custom_fig, master=right)
        self.custom_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.custom_canvas, right)
        toolbar.update()
        toolbar.pack(fill=tk.X)

    def _toggle_cycle_entry(self):
        if self.cycle_mode.get() == "selected":
            self.cycle_entry.config(state="normal")
            if self.cycle_entry.get().startswith("e.g."):
                self.cycle_entry.delete(0, tk.END)
        else:
            self.cycle_entry.config(state="disabled")

    def _populate_custom_tab(self):
        if self.df is None:
            return
        numeric_cols = [c for c in self.df.columns if self.df[c].dtype.kind in ("i", "f")]
        all_cols = list(self.df.columns)

        self.custom_x["values"] = numeric_cols
        self.custom_y["values"] = numeric_cols

        # Set sensible defaults
        if "relative_time_s" in numeric_cols:
            self.custom_x.set("relative_time_s")
        elif numeric_cols:
            self.custom_x.set(numeric_cols[0])

        if "voltage_V" in numeric_cols:
            self.custom_y.set("voltage_V")
        elif len(numeric_cols) > 1:
            self.custom_y.set(numeric_cols[1])

    def _parse_cycle_selection(self) -> Optional[list]:
        """Parse the cycle entry field. Returns list of cycle numbers or None for all."""
        if self.cycle_mode.get() == "all":
            return None

        text = self.cycle_entry.get().strip()
        if not text or text.startswith("e.g."):
            return None

        cycles = set()
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    lo, hi = part.split("-", 1)
                    for c in range(int(lo), int(hi) + 1):
                        cycles.add(c)
                except ValueError:
                    pass
            else:
                try:
                    cycles.add(int(part))
                except ValueError:
                    pass
        return sorted(cycles) if cycles else None

    def _get_filtered_df(self) -> pd.DataFrame:
        """Return the DataFrame filtered by cycle selection."""
        if self.df is None:
            return pd.DataFrame()

        selected = self._parse_cycle_selection()
        if selected is None or "cycle" not in self.df.columns:
            return self.df

        return self.df[self.df["cycle"].isin(selected)]

    def _draw_custom_plot(self):
        """Draw the custom plot on the embedded canvas."""
        self.custom_ax.clear()

        x_col = self.custom_x.get()
        y_col = self.custom_y.get()
        if not x_col or not y_col:
            messagebox.showwarning("Select Axes", "Pick both X and Y columns.")
            return False

        plot_df = self._get_filtered_df()
        if plot_df.empty:
            messagebox.showwarning("No Data", "No data matches the current selection.")
            return False

        style = self.custom_style.get()
        color_by = self.custom_color_status.get()

        if color_by and "status" in plot_df.columns:
            for status, group in plot_df.groupby("status"):
                color = STATUS_COLORS.get(status, "#333333")
                if style == "line":
                    self.custom_ax.plot(group[x_col], group[y_col],
                                        linewidth=0.8, alpha=0.8, color=color, label=status)
                else:
                    self.custom_ax.scatter(group[x_col], group[y_col],
                                            s=2, alpha=0.5, color=color, label=status)
            self.custom_ax.legend(loc="best")
        else:
            if style == "line":
                self.custom_ax.plot(plot_df[x_col], plot_df[y_col],
                                    linewidth=0.8, alpha=0.8, color="#1f77b4")
            else:
                self.custom_ax.scatter(plot_df[x_col], plot_df[y_col],
                                        s=2, alpha=0.5, color="#1f77b4")

        # Title
        selected = self._parse_cycle_selection()
        title_suffix = ""
        if selected:
            if len(selected) <= 5:
                title_suffix = f"  (Cycles {', '.join(str(c) for c in selected)})"
            else:
                title_suffix = f"  (Cycles {selected[0]}–{selected[-1]}, n={len(selected)})"

        self.custom_ax.set_xlabel(x_col)
        self.custom_ax.set_ylabel(y_col)
        self.custom_ax.set_title(f"{y_col} vs {x_col}{title_suffix}")
        self.custom_ax.grid(True, alpha=0.3)
        self.custom_fig.tight_layout()
        self.custom_canvas.draw()
        return True

    def _preview_plot(self):
        if self.df is None:
            messagebox.showwarning("No Data", "Load a file first.")
            return
        self._draw_custom_plot()

    def _save_custom_plot(self):
        if self.df is None:
            messagebox.showwarning("No Data", "Load a file first.")
            return

        if not self._draw_custom_plot():
            return

        path = filedialog.asksaveasfilename(
            title="Save Plot",
            defaultextension=".png",
            initialfile="custom_plot.png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
        )
        if not path:
            return

        self.custom_fig.savefig(path, dpi=300)
        messagebox.showinfo("Saved", f"Plot saved at 300 dpi:\n{path}")


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = BatteryGUI()
    app.mainloop()
