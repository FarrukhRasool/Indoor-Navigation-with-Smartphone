# How to Run This Project

- **Python 3.11 or newer** (developed on 3.13).
- The following Python packages:
  - `numpy`
  - `pandas`
  - `matplotlib`
  - `scipy`
  - `openpyxl` (pandas uses it to read the reference spreadsheet)
  - `jupyter` (to run the notebooks)

Install them all with:

```bash
pip install numpy pandas matplotlib scipy openpyxl jupyter
```

---

## Running against a *new* recording

The four runs above are the fixed test dataset. If you ever want to run the
pipeline on a **new** recording from the same app, note that a few things are
tied to these specific runs and would need updating first:

- Put the new file in `data/raw/` named `Record_data_path_<N>.csv`.
- Add its **start position, start floor, and initial heading** to `RUN_START` in
  `src/preprocessing.py` (these are calibrated per run).
- Add its **reference checkpoints** to `assignment/Paths_references.xlsx` and its
  column positions to `REFERENCE_COLUMNS` in `src/evaluation.py`.

For simply reproducing the assignment's results, you can ignore this section.

--