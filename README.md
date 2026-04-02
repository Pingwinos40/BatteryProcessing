# BatteryProcessing

Tkinter GUI tool for processing and plotting raw battery cycler data (.xls/.xlsx) from Chinese-language battery testers.

### What it does

1. **Load** — Opens raw .xls/.xlsx files via a file picker. Automatically skips the first (Info) and last (Cycle) sheets, concatenates all middle Detail sheets, and translates Mandarin headers and status labels to English.
2. **Export** — Saves the processed, translated data as a clean CSV.
3. **Batch Plot** — Generates per-cycle Voltage vs Time and Voltage vs Capacity plots (colored by charge/discharge status), exported as 300 dpi PNGs. Supports line or scatter style.
4. **Custom Plot** — Pick any X/Y axes, filter by cycle range, toggle line/scatter and color-by-status, preview in an embedded plot window, and save as 300 dpi PNG.

### Requirements

- Python 3.8+
- Install dependencies: `pip install -r requirements.txt`

### Usage

```
python battery_gui.py
```

No command-line arguments needed — everything is done through the GUI.

### AI Use

I used generative AI tools (Claude Opus 4.6, Gemini 3) for generating and refining this battery analysis tool.
