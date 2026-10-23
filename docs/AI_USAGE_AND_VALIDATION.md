# AI Usage and Validation Record

## 1. Project Overview

**Project:** A-Share Market State Research

**Purpose:** Build a Streamlit prototype that retrieves A-share market data, summarizes major index performance, and evaluates market breadth subject to explicit data-quality checks.

**Development approach:** AI-assisted development with local execution, inspection, testing, and iterative debugging.

## 2. How AI Was Used

AI assistance was used to support the following development activities:

- Structuring the application and organizing Python modules.
- Drafting and refining API request and response handling.
- Implementing descriptive market-breadth calculations.
- Adding input validation, missing-value handling, duplicate checks, and timestamp consistency checks.
- Drafting unit tests and assisting with debugging.
- Improving the Streamlit interface and project documentation.
- Preparing local execution and future deployment instructions.

AI-generated suggestions were not treated as proof of correctness. Code was executed locally, and results were checked against test output and actual API responses.

## 3. Data Source and Handling

The application uses the Fuyao Financial API.

Documentation consulted:

- https://fuyao.aicubes.cn/docs/quickstart/
- https://fuyao.aicubes.cn/docs/api-reference/a-share-index/
- https://github.com/HiThink-Tech/Financial-API/blob/main/skills/hithink-finance/references/api/endpoints-prices.md

The application requests major index snapshots and paginated A-share stock snapshots.

The stock response is checked for issues including:

- Missing or invalid stock codes.
- Duplicate stock codes.
- Differences between reported and received record counts.
- Missing or invalid percentage-change values.
- Inconsistent page timestamps.

API credentials are supplied through an environment variable locally and are intended to be configured through deployment secrets in a hosted environment.

## 4. Validation Performed

### Local code checks

The following commands were executed successfully during local development:

```powershell
python -m py_compile .\app.py
python -m py_compile .\src\market_data.py
python -m unittest discover -s tests -v
```

The latest recorded unit-test run completed with **23 tests passing**.

The tests cover time-gap handling, market-breadth calculations, market-data validation, and index-data quality checks.

### Live API smoke test

A real API request successfully retrieved:

- 5,578 stock records.
- 5,570 records with valid percentage-change values.
- 8 records with missing percentage-change values.
- Three major index records.

These figures describe one observed API response and are not guaranteed to remain the same.

## 5. Important Finding: Pagination Timestamp Inconsistency

The observed stock snapshot contained different timestamps across pages. The index response timestamp also differed from the stock response timestamp by approximately three seconds in the recorded run.

These differences do not, by themselves, prove that the underlying prices are inconsistent. However, the available evidence does not establish that all pages represent one atomic market snapshot.

The application therefore does not present a formal market-breadth conclusion when the page timestamps fail its consistency check.

This is an intentional limitation designed to avoid overstating the reliability of a derived statistic.

Potential follow-up work includes investigating whether the provider supports a more suitable consistent snapshot endpoint, documenting the provider's timestamp semantics more precisely, and testing behavior across trading and non-trading sessions.

The timestamp check should not be removed merely to make the interface display a breadth result.

## 6. Limitations of Validation

The checks performed so far do not establish that:

- All API data corresponds to the current trading session.
- All endpoints share an atomic snapshot.
- The application has been validated across all market conditions.
- The descriptive statistics have predictive power.
- The hosted deployment works correctly in every environment.

A successful API response is not sufficient evidence that the returned data is current or suitable for every analytical conclusion.

## 7. Security and Reproducibility

- API credentials should be supplied through environment variables or the hosting platform's secrets mechanism.
- Credentials must not be committed to source code or public documentation.
- Local virtual environments, caches, and generated data are excluded through `.gitignore`.
- Before publication, inspect both the current files and Git history for accidentally committed credentials.
- Re-run the unit tests after material changes.

## 8. AI-Assisted Development Disclosure

AI tools were used to assist with implementation, debugging, testing design, and documentation. The developer ran the application and validation commands locally and used observed outputs to identify limitations.

This record describes the development and validation evidence available at the time of writing. It should be updated when additional tests, provider investigations, or deployment checks are completed.

## 9. Publication Status

At the time this record was prepared, a successful public GitHub publication and hosted Streamlit deployment had not yet been verified.

The project should only be described as publicly deployed after the repository and hosted application have been confirmed to work.