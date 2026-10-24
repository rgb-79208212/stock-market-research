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

## 10. Publication and Deployment Status

Local automated tests have passed as recorded above.

A passing local test suite does not prove that the latest local commits have been pushed to the public repository or that a hosted Streamlit application is available and functioning.

Public repository synchronization, credential-history review, and hosted deployment must be independently verified before the project is described as publicly deployed.
