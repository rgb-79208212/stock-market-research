# AI Usage and Validation Record

## 1. Project Overview

**Project:** A-Share Market State Research

**Purpose:** Build a Streamlit prototype that retrieves A-share market data, summarizes major index performance, evaluates market breadth subject to explicit data-quality checks, and presents a transparent descriptive market-state classification.

**Development approach:** AI-assisted development combined with local code inspection, automated tests, API diagnostics, and iterative debugging.

**Research boundary:** The application is a descriptive research prototype. Its output is not a price forecast, investment recommendation, position-sizing instruction, or trading signal.

## 2. How AI Was Used

AI assistance was used to support:

- Structuring the application and organizing Python modules.
- Drafting and refining API request and response handling.
- Implementing descriptive market-breadth calculations.
- Adding input validation, missing-value handling, duplicate checks, and timestamp consistency checks.
- Designing automated tests and assisting with debugging.
- Improving the Streamlit interface and project documentation.
- Reviewing research-quality gates, freshness checks, and applicability limitations.

AI-generated suggestions were not treated as proof of correctness. The developer ran code locally, inspected actual API responses, reviewed implementation details, and used automated test results to identify issues.

### Concrete corrections made to AI-generated output

The following are representative examples where AI-suggested implementations were inspected, tested, and corrected before merging:

1. **Secret resolution on Streamlit Cloud.**
   AI-drafted code read API keys only via `os.getenv(...)`. Streamlit Community Cloud exposes Secrets through `st.secrets`, not through process environment variables, so the AI interpretation button would fail in production while passing locally.
   *Correction*: introduced `_read_config(name, default)` in `src/llm_analysis.py` that prefers `st.secrets`, falls back to `os.environ`, and calls `load_dotenv(override=False)` at module import so both local `.env` and hosted Secrets resolve through one code path.

2. **Title obscured by the fixed header.**
   AI-generated CSS set `.block-container { padding-top: 1rem; }`, which placed the page title underneath Streamlit's fixed `stHeader` bar. The page looked broken on first load.
   *Correction*: made `header[data-testid="stHeader"]` transparent and raised `.block-container` top padding to `3.5rem`; the header menu stays clickable while the title is fully visible.

3. **Overly broad `.gitignore` rule.**
   A suggested rule `*.txt` would have silently excluded `requirements.txt`, breaking hosted builds.
   *Correction*: replaced with targeted patterns (`/apptemp.txt`, `/*_temp.txt`) plus export-data patterns (`*.csv`, `*.xlsx`, `*.parquet`), and re-verified with `git status --ignored` that `.env`, `.venv/`, `__pycache__/`, and `data/` are ignored while required files remain tracked.

4. **Conflating "quality passed" with "market is live".**
   An early UI draft displayed a single "data OK" banner once checks passed, which implied the snapshot was a real-time trading observation. Quality checks do not establish trading-session validity.
   *Correction*: split the state into four independent badges (data quality / freshness / trading session / snapshot time) and gated downstream conclusions on each separately, so a passing quality check no longer implies a confirmed live session.

5. **Silent stale-data reuse.**
   An early prototype reused previously fetched snapshot results when a new request failed, which could present outdated data as current.
   *Correction*: on every fetch the app now clears `market_result` / `index_result` / error keys from `st.session_state` before requesting, and refuses to generate formal breadth or state conclusions when freshness or quality gates fail.

AI-generated market interpretation is conditional on the supplied research report and its evidence. A successful model response does not independently verify the correctness, completeness, freshness, or predictive value of the underlying data.

## 3. Data Sources and Handling

The application uses the Fuyao Financial API.

Documentation consulted:

- https://fuyao.aicubes.cn/docs/quickstart/
- https://fuyao.aicubes.cn/docs/api-reference/a-share-index/
- https://fuyao.aicubes.cn/docs/api-reference/prices/
- https://github.com/HiThink-Tech/Financial-API/blob/main/skills/hithink-finance/references/api/endpoints-prices.md

The application requests paginated A-share stock snapshots and major index snapshots. Historical-data diagnostic scripts also query daily history for selected stocks.

Checks implemented in the tracked application code include:

- Missing or invalid stock codes.
- Duplicate stock codes.
- Differences between reported and received record counts.
- Missing or invalid percentage-change values.
- Invalid or inconsistent stock snapshot page timestamps.
- Stock/index timestamp gaps and snapshot freshness.
- Required research-quality gates before producing dependent conclusions.

The stock snapshot timestamp is treated as a data-provider timestamp, not proof that all securities share one last-trade time or that all pages form an atomic snapshot.

API credentials are loaded through environment configuration and must not be committed to source code, documentation, tests, or repository history.

## 4. Automated Tests

### Latest confirmed full test run

Command:

```powershell
python -m pytest -q
```

Observed result:

```text
101 passed, 21 subtests passed in 2.02s
```

This result confirms that the automated tests passed in that local run. It does not prove correctness under every API response, market condition, operating environment, or deployment configuration.

Previously recorded test counts in this document or other project documentation should not be treated as current when they differ from the result above.

### Test areas

The existing test suite covers relevant areas of market-data handling, market breadth, market-state rules, data-quality gates, timestamp freshness, applicability checks, research-report construction, and AI interpretation validation.

Tests help establish expected behavior for covered cases. They do not substitute for official trading-calendar verification, complete historical market data, or an independently designed backtest.

## 5. Live API and Historical-Data Diagnostics

The repository contains local diagnostic scripts for:

- Stock and index snapshot requests.
- Historical daily data for a selected stock.
- Historical daily data for a small cross-section of eight stocks.
- Historical query ranges and segmented-query comparisons.
- API pagination and timestamp behavior.

These scripts are diagnostic utilities, not a production historical data pipeline. Their output depends on the query interval, API permissions, upstream availability, and the time the scripts are run.

An earlier validation record reported one stock snapshot containing 5,578 records, including 5,570 records with valid percentage-change values and 8 records with missing percentage-change values. The date of that observation was not recorded in this document. These figures are historical observations only and must not be presented as current market counts.

The recorded snapshot investigation also found differing timestamps across stock pages and a small time gap between stock and index snapshots. Those observations motivated stricter timestamp consistency checks. A timestamp mismatch does not by itself prove that prices are wrong, but it means the available evidence does not establish that the combined data is one atomic snapshot.

Historical daily data for eight selected stocks, even when available for approximately one year, cannot establish full-market breadth or validate the market-state thresholds. No formal historical validation is claimed in this record.

## 6. Market-State Rules and Validation Limits

The current rule-based market-state classification combines:

- The percentage of stocks with positive percentage changes.
- The percentage of stocks with negative percentage changes.
- The directions of three major indices.
- Explicit thresholds defined in `src/market_state.py`.

The thresholds are transparent implementation choices for the first prototype. The method metadata explicitly records:

```python
"historically_validated": False
```

No predictive performance claim is made.

A formal historical validation would require, at minimum:

1. A clearly defined historical sample period and reproducible source data.
2. Adequate market-wide observations for each evaluation date.
3. Explicit handling of missing records, trading calendars, timestamp consistency, and universe changes.
4. A documented rule implementation and evaluation procedure.
5. Results that can be reproduced from the documented inputs and method.

Until that work is completed, historical daily data diagnostics must not be described as a successful backtest.

## 7. Data Quality, Freshness, and Applicability

The application applies explicit quality gates before generating dependent research conclusions. A missing, invalid, stale, or inconsistent snapshot should not silently be treated as valid.

Freshness checks compare reported timestamps against a reference time. This is not equivalent to verifying an official exchange trading session.

The current session assessment identifies weekends and regular intraday time windows. The project has not established full official trading-calendar verification for holidays, special closures, or exceptional sessions. Calendar verification must remain unconfirmed until backed by a reliable calendar source.

A timestamp gap between endpoints, or a page-timestamp inconsistency, should be reported as a limitation rather than silently ignored.

## 8. Security and Reproducibility

- API credentials should be supplied through environment variables, a local environment file excluded from Git, or the hosting platform's secrets mechanism.
- Credentials must not be committed to source code, tests, public documentation, or generated reports.
- Local virtual environments, caches, and generated data are excluded through `.gitignore`.
- Ignoring a file in the current working tree does not prove that it was never committed in Git history.
- Before publication, inspect tracked files, staged changes, and commit history for accidentally committed credentials.
- Re-run the full test suite after material code changes.
- Record the actual command and output for any new live API or historical validation.

## 9. AI-Assisted Development Disclosure

AI tools assisted with implementation, debugging, test design, code review, and documentation. The developer executed local tests and diagnostic commands and used the observed results to refine the implementation.

AI-generated interpretations remain subject to the quality, freshness, completeness, and applicability of their input data. Model-generated prose is not an independent data source or proof of a research conclusion.

This record describes the validation evidence currently documented in the repository. It should be updated when new tests, historical validation, security audits, or deployment checks are completed.

The concrete corrections listed in §2 are the primary evidence that AI output was reviewed rather than accepted verbatim.

## 10. Publication and Deployment Status

- **Public repository**: `https://github.com/rgb-79208212/stock-market-research` (`main` branch synchronized).
- **Hosted application**: `https://stock-market-research-ygbtfnt7pgmndj6e9eoz7k.streamlit.app`
- **Hosting platform**: Streamlit Community Cloud, Python 3.12.
- **Secrets configured on the hosting platform**: `HITHINK_FINANCE_API_KEY`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` (values are not recorded in this document).
- **Credential handling**: API keys were rotated after an accidental local exposure during development. Only the rotated keys are configured locally and on the hosting platform. No credentials are tracked in Git.
- **Automated test status**: `101 passed, 21 subtests passed` — see `docs/TESTING.md` §2 for the latest confirmed run.
- **Post-deployment manual checks**: snapshot retrieval, diagnostics tabs, and AI interpretation generation are verified against the hosted URL.

The hosted deployment reflects the current `main` branch. Any later commit triggers an automatic redeploy; the manual checklist in `docs/TESTING.md` §5 should be repeated after material changes.


## Additional Historical Data Validation (2026-10-24)

### Scope and method

A sample-level structural and trading-date consistency check was performed on historical daily records for six A-share stocks:

- Kweichow Moutai (600519.SH)
- Ping An Insurance (601318.SH)
- Ping An Bank (000001.SZ)
- Wuliangye (000858.SZ)
- Contemporary Amperex Technology (300750.SZ)
- BYD (002594.SZ)

The retrieved sample for each stock contained 241 records, covering 2025-10-27 through 2026-10-23, with 241 unique dates.

### Observed results

- No invalid or duplicate dates were detected in these six samples.
- No missing values were detected in the checked open, high, low, close, volume, and turnover fields.
- Prices were positive; volume and turnover had no negative values.
- No violations of the checked OHLC price relationships were detected.
- The six stocks had matching date sets.
- Their date sets matched the reference trading-date set obtained from AkShare's Sina-derived trading calendar over the same historical interval. No suspected missing dates or dates outside that reference calendar were detected.

### Limitations

This is a limited sample-level consistency check, not a market-wide completeness audit or an official exchange certification. The reference calendar is a third-party data source, not direct confirmation from the exchanges. These checks do not independently establish the numerical accuracy, adjustment methodology, corporate-action treatment, or real-time availability of every field. Results should not be interpreted as proof that all A-share instruments or all historical periods are complete and correct.
