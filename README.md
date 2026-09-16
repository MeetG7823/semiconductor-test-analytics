# Semiconductor Test Yield & Failure Analysis

An AI-assisted educational portfolio project for Meet Gondalia, Computer Engineering, Iowa State University.

**Question:** Can a reproducible analysis identify a simulated lot-level leakage shift, quantify its effect on observed yield, and distinguish electrical failures from corrupted records?

**Implemented:** synthetic CSV generation, validation/quarantine, SQLite analytics, a Streamlit dashboard, downloadable CSVs, an offline HTML report, and six calculation/validation tests.

**Not implemented:** ML prediction, PySpark, cloud deployment, real instrumentation, device physics simulation, or real production validation. This project has no affiliation with any company data or specifications.

## Windows quick start

Extract the ZIP first. Open the extracted folder containing `app.py`, `pipeline.py`, and this README. In File Explorer, click the address bar, type `powershell`, and press Enter. Run one command at a time:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe pipeline.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Python 3.12 or 3.13 is a good choice for the pinned dependencies. If `py` is unavailable but `python --version` works, use `python` for the first two commands. If neither works, install Python from https://www.python.org/downloads/windows/ and reopen PowerShell. Do not change execution policy: these commands invoke the environment directly without activation.

The browser should open http://localhost:8501. Keep the terminal open; Ctrl+C stops the server. After setup, only the final command is needed to reopen the dashboard. The pipeline overwrites generated data and outputs when rerun.

**Immediate fallback:** double-click `outputs/report.html`. The included report works offline with no Python installation. It contains the verified default results, a yield chart, lot details, and limitations. You can print it to PDF from the browser if desired.

## Default results (seed 42)

| Metric | Result |
|---|---:|
| Original unique devices | 12,000 |
| Raw rows, including duplicate exports | 12,020 |
| Valid devices | 11,900 |
| Quarantined rows | 120 |
| Unique devices without a valid result | 100 |
| Passing valid devices | 10,768 |
| Failing valid devices | 1,132 |
| Observed valid-device yield | 90.49% |
| Lowest-yield lot | L12: 47.80% |

These results describe synthetic data. They are not measured semiconductor product performance or a demonstrated yield improvement. Different seeds change the results.

## Understand the experiment

- Twelve sequential lots, four wafers per lot, 250 devices per wafer.
- Each device is measured once at a randomly assigned temperature (-40, 25, or 85 °C) and supply (3.0, 3.3, or 3.6 V). Different temperature groups contain different devices.
- Leakage follows a positive numerical model with temperature effects, wafer offsets, and measurement variation. Lots L09–L12 receive an increasing injected offset.
- Random defects increase leakage/current or decrease illustrative gain. These are valid observations that can fail the specifications.
- Deliberate data corruption: 25 missing leakage values, 25 nonnumeric current values, 25 negative leakage values, 25 invalid temperature settings, and 20 exact duplicate exports.
- The 100 corrupt original records are placed in L01. Thus its observed yield covers only 900 valid devices, and exclusions can bias comparisons. This placement is disclosed rather than interpreted as a process problem.

### Illustrative specifications

PASS requires all three: leakage ≤ 10 µA, current ≤ 60 mA, gain ≥ 18 dB. A device exactly at a limit passes. These are educational thresholds. A device can fail more than one limit.

`dc_power_mw = voltage_v × current_ma`: volts × milliamps = milliwatts. This is DC electrical input power, not RF output power, efficiency, or power-added efficiency.

### Validation versus specification testing

Missing, nonfinite, negative-magnitude, nonnumeric, duplicate, and unsupported-setpoint records are quarantined with reasons. A very high, finite, positive leakage reading remains valid and counts as a failure. The supported-setpoint rule is specific to this generated experiment.

There is one test run. The first occurrence of a device ID is considered authoritative; later occurrences are quarantined. A real dataset with legitimate retests requires a test-run/condition key and a documented first-pass or final-pass yield policy. This implementation does not reconcile retests.

### Yield and denominators

Observed yield = passing valid unique devices / all valid unique devices × 100.

100 unique devices have no valid result; their outcomes are unknown. The 20 duplicate rows do not add devices. Quarantine count is a record count, not a count of failing devices. The dashboard reports these counts separately.

The result is yield at the sampled conditions, not all-temperature qualification yield. Match temperature and voltage when comparing lots; association alone is not a physical root cause.

## Read the code in this order

1. `pipeline.py` → `generate()`: how data and known faults are constructed.
2. `classify()`: threshold comparisons and multi-label failures.
3. `validate()`: numeric parsing, finite checks, duplicate tracking, and quarantine.
4. `sql/analytics.sql`: COUNT, SUM, GROUP BY, and the yield denominator. The Boolean SUM expressions use SQLite syntax.
5. `analyze()` and `run()`: actual CSV input, SQL execution, output exports, database and report creation.
6. `app.py`: filters, view-specific metrics, and charts. SQL produces the saved summaries; the interactive app recalculates filtered summaries with pandas.
7. `tests/test_pipeline.py`: boundary cases, known 50% yield, missing/corrupt records, and reconciliation.

## Three-hour learning and demo plan

| Time | Task |
|---|---|
| 0–25 min | Extract, set up Python, run pipeline and dashboard. Use offline report if installation stalls. |
| 25–65 min | Read generation, validation, and SQL. Recalculate one lot's yield from its counts. |
| 65–100 min | Explore matching temperature/voltage filters; explain why L12 looks different. |
| 100–125 min | Run tests. Try `pipeline.py --seed 7`, compare the results, then restore `pipeline.py --seed 42`. |
| 125–150 min | Capture screenshots of overview, matching-condition leakage, and quality accounting. |
| 150–180 min | Rehearse a one-minute demo and questions for summer-internship recruiters. |

Do not add technologies you cannot explain merely to fill a skills list.

## One-minute demonstration sequence

1. Show all-data yield and the denominator. State that the dataset is synthetic.
2. Identify L12 as the lowest-yield lot.
3. Set temperature to 85 °C and supply to 3.3 V; compare L01 and L12 using the lot selector.
4. Open Measurement detail. Explain the median leakage, percentile band, and upper limit.
5. Open Data quality & method. Explain why corrupt records and valid failed devices are handled differently.
6. Explain what a real investigation would need: calibration checks, repeat measurements, more process context, and hardware access.

## Recruiter preparation

Be accurate about AI assistance and your own contribution. After running and understanding the project, discuss the decisions you can defend: denominator choice, duplicate handling, limit boundaries, source of the simulated drift, and the limits of the analysis. Do not claim real silicon testing, production-scale processing, predictive ML, or improved manufacturing yield.

Questions to explore with recruiters:

- Which summer teams combine Python automation with device characterization or test-data analysis?
- What hardware or measurement skills would make this project more relevant to your team's work?
- Which summer requisition best fits a Computer Engineering student with this software/data background?

For work authorization, provide accurate answers to application questions and consult your school's international-student adviser about your situation. This project and an internship posting do not establish future OPT eligibility or employer sponsorship.

## References

- Streamlit setup: https://docs.streamlit.io/get-started/installation/command-line
- Streamlit module launch: https://docs.streamlit.io/develop/concepts/architecture/run-your-app


## Verification

Prepared and executed on Python 3.12 in Linux, using Streamlit 1.64.0, pandas 2.2.3, and Altair 5.5.0. The Windows commands are provided for local setup; this package has not been executed on your Windows machine. Six standard-library tests pass. Dashboard default loading, temperature/voltage/lot filtering, outcome filtering, and empty selection are checked using Streamlit AppTest.
