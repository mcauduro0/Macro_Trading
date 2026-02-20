# Phase 3: Extended Connectors - Research

**Researched:** 2026-02-19
**Domain:** Extended data connectors -- BCB Focus, B3/Tesouro Direto, IBGE SIDRA, STN Fiscal, CFTC COT, US Treasury, BCB FX Flow
**Confidence:** HIGH

## Summary

Phase 3 extends the data ingestion layer from Phase 2's four core connectors (BCB SGS, FRED, Yahoo Finance, BCB PTAX) to seven additional connectors, completing coverage across all 11 data sources required for the 200+ series universe. The new connectors span three distinct API patterns: (1) OData-based APIs (BCB Focus, partially STN), (2) JSON REST APIs (IBGE SIDRA, Tesouro Direto), and (3) bulk CSV file downloads (CFTC COT, US Treasury yields). Each connector writes to different target tables -- `macro_series`, `curves`, `fiscal_data`, and `flow_data` -- using the established BaseConnector ABC, `_bulk_insert` with ON CONFLICT DO NOTHING, and respx-based test mocking.

The most technically complex connectors are BCB Focus (OData pagination across multiple expectation endpoints), CFTC COT (parsing bulk CSV files with 200+ columns), and B3/Tesouro Direto (combining BCB SGS series #7805-7816 for the DI swap curve with Tesouro Direto JSON for NTN-B real rates). The BCB FX Flow and STN Fiscal connectors are simpler, both primarily fetching from BCB SGS series with slightly different target tables (`flow_data` and `fiscal_data` respectively). The US Treasury connector fetches structured CSV data from Treasury.gov and maps it to the `curves` table.

All seven connectors follow the exact same lifecycle as the existing Phase 2 connectors: inherit from `BaseConnector`, override `SOURCE_NAME`/`BASE_URL`, implement `fetch()` and `store()`, use `_bulk_insert()` for idempotent writes, and maintain the `_ensure_data_source()` / `_ensure_series_metadata()` metadata registration pattern. Tests use respx mocking with JSON fixture files.

**Primary recommendation:** Implement connectors in order of dependency and complexity -- BCB FX Flow first (simplest, reuses BCB SGS API pattern), then B3/Tesouro Direto (DI curve), IBGE SIDRA, STN Fiscal, BCB Focus (OData pagination), US Treasury, and CFTC COT (bulk CSV) last. Each connector gets its own test file with respx mocks.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONN-04 | BCB Focus connector fetches market expectations (IPCA, Selic, GDP, FX) by horizon with OData pagination | BCB Focus OData API at `olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/`, 6+ entity sets (Annual, Monthly, Selic, Top5, Inflation12M), paginate with `$top=1000&$skip=N`, store in `macro_series` table with series like `BR_FOCUS_IPCA_{YEAR}_MEDIAN` |
| CONN-05 | B3/Tesouro Direto connector fetches DI swap curve (BCB SGS #7805-7816) and NTN-B real rates from Tesouro Direto JSON API | DI swap curve from BCB SGS series 7805-7816 (12 tenors, 30d-360d), NTN-B real rates from Tesouro Direto JSON at `tesourodireto.com.br/json/...` or CSV fallback, store in `curves` table with `curve_id='DI_PRE'` and `curve_id='NTN_B_REAL'` |
| CONN-06 | IBGE SIDRA connector fetches IPCA disaggregated by 9 components with weights | IBGE SIDRA API at `apisidra.ibge.gov.br/values/t/7060/...`, Table 7060 with Variable 63 (MoM %) and Variable 2265 (weight), Classification 315 for 9 IPCA groups, store in `macro_series` |
| CONN-07 | STN Fiscal connector fetches primary balance, debt composition, revenue/expenditure from BCB SGS + Tesouro Transparente | 4 BCB SGS fiscal series (5364, 21864, 21865, 7620), Tesouro Transparente API at `apidatalake.tesouro.gov.br` for debt composition, store in `fiscal_data` table with `fiscal_metric` column |
| CONN-08 | CFTC COT connector fetches disaggregated positioning for 12 contracts x 4 categories (48 series) from bulk CSV files | Disaggregated Futures Only bulk CSVs: `cftc.gov/files/dea/history/fut_disagg_txt_{YYYY}.zip`, current via Socrata API `publicreporting.cftc.gov/resource/72hh-3qpy.csv`, parse 200+ columns, compute net positions for 4 categories x 12 contracts, store in `flow_data` |
| CONN-09 | US Treasury connector fetches daily nominal, real (TIPS), and breakeven yield curves from Treasury.gov CSV | Treasury.gov CSV by year: `home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{YYYY}?type=daily_treasury_yield_curve&...`, also `daily_treasury_real_yield_curve` for TIPS, compute breakeven, store in `curves` with `curve_id='UST_NOM'`, `'UST_REAL'`, `'UST_BEI'` |
| CONN-12 | BCB FX Flow connector fetches commercial/financial flows and BCB swap stock from SGS series | 4 BCB SGS series: 22704 (commercial flow), 22705 (financial flow), 22706 (total flow), 12070 (BCB swap stock), reuse BCB SGS API pattern, store in `flow_data` table with `flow_type` column |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | Async HTTP client | Already in use by Phase 2 connectors; connection pooling, timeout control |
| tenacity | 9.1.4 | Retry with backoff | AsyncRetrying pattern established in BaseConnector; exponential backoff + jitter |
| structlog | >=24.4.0 | Structured logging | Already configured for all connectors via `self.log` binding |
| pandas | >=2.1 | CSV parsing for CFTC/Treasury | Already in pyproject.toml; needed for large CSV parsing of CFTC bulk files and Treasury yield data |
| respx | 0.22.0 | HTTPX test mocking | Established test pattern from Phase 2 connector tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| zipfile (stdlib) | N/A | Extracting CFTC ZIP archives | CFTC historical data comes as yearly ZIP files containing CSVs |
| io (stdlib) | N/A | In-memory CSV parsing | CFTC and Treasury CSV data parsed without writing temp files |
| csv (stdlib) | N/A | CSV reading | Treasury.gov CSV files; pandas also suitable |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pandas for CFTC CSV | polars | polars is faster but pandas is already a dependency and CFTC data volume is modest (~100K rows/year) |
| Raw httpx for Tesouro Direto | python-bcb library | python-bcb wraps Focus/PTAX but adds a dependency; raw httpx is consistent with other connectors |
| CFTC Socrata API | CFTC bulk ZIP files | Socrata provides filtered access but no token needed; ZIP gives complete data with no API limits. Use both: ZIP for historical, Socrata for current week |

**Installation:**
No new dependencies required. All libraries are already in pyproject.toml from Phase 1 and Phase 2.

## Architecture Patterns

### Recommended Project Structure
```
src/
  connectors/
    __init__.py          # Add new connector exports
    base.py              # BaseConnector ABC (unchanged)
    bcb_sgs.py           # (Phase 2, unchanged)
    bcb_ptax.py          # (Phase 2, unchanged)
    fred.py              # (Phase 2, unchanged)
    yahoo_finance.py     # (Phase 2, unchanged)
    bcb_focus.py         # NEW: BCB Focus market expectations (CONN-04)
    b3_market_data.py    # NEW: B3/Tesouro Direto DI curve + NTN-B (CONN-05)
    ibge_sidra.py        # NEW: IBGE SIDRA IPCA by component (CONN-06)
    stn_fiscal.py        # NEW: STN Fiscal data (CONN-07)
    cftc_cot.py          # NEW: CFTC COT positioning (CONN-08)
    treasury_gov.py      # NEW: US Treasury yield curves (CONN-09)
    bcb_fx_flow.py       # NEW: BCB FX Flow data (CONN-12)
tests/
  connectors/
    test_bcb_focus.py    # NEW
    test_b3_market_data.py   # NEW
    test_ibge_sidra.py   # NEW
    test_stn_fiscal.py   # NEW
    test_cftc_cot.py     # NEW
    test_treasury_gov.py # NEW
    test_bcb_fx_flow.py  # NEW
  fixtures/
    bcb_focus_sample.json        # NEW
    tesouro_direto_sample.json   # NEW
    ibge_sidra_sample.json       # NEW
    stn_fiscal_sample.json       # NEW
    cftc_disagg_sample.csv       # NEW
    treasury_yield_sample.csv    # NEW
    bcb_fx_flow_sample.json      # NEW
```

### Pattern 1: BCB SGS Reuse for Simple Connectors (BCB FX Flow)
**What:** BCB FX Flow and the DI swap curve portion of B3 connector both fetch from BCB SGS API endpoints -- the same API pattern already implemented in `BcbSgsConnector`.
**When to use:** Connectors that fetch from BCB SGS but store to different tables (`flow_data`, `curves` instead of `macro_series`).
**Implementation approach:** These connectors should NOT inherit from BcbSgsConnector. Instead, they inherit from BaseConnector with `BASE_URL = "https://api.bcb.gov.br"` and replicate the fetch logic (same URL pattern, same DD/MM/YYYY date format, same value parsing) but override `store()` to write to the appropriate table (`flow_data`, `curves`).

```python
class BcbFxFlowConnector(BaseConnector):
    SOURCE_NAME = "BCB_FX_FLOW"
    BASE_URL = "https://api.bcb.gov.br"
    RATE_LIMIT_PER_SECOND = 3.0

    FX_FLOW_SERIES = {
        "BR_FX_FLOW_COMMERCIAL": 22704,
        "BR_FX_FLOW_FINANCIAL": 22705,
        "BR_FX_FLOW_TOTAL": 22706,
        "BR_BCB_SWAP_STOCK": 12070,
    }

    async def fetch(self, start_date, end_date, **kwargs):
        # Same BCB SGS URL pattern as BcbSgsConnector.fetch_series()
        # Uses /dados/serie/bcdata.sgs.{code}/dados
        ...

    async def store(self, records):
        # Store to flow_data table (not macro_series)
        # Uses FlowData model with flow_type column
        return await self._bulk_insert(
            FlowData, records, "uq_flow_data_natural_key"
        )
```

### Pattern 2: OData Pagination for BCB Focus
**What:** The BCB Focus API uses OData protocol with server-side pagination. The connector must page through results using `$top` and `$skip`.
**When to use:** BCB Focus connector (CONN-04). Also potentially relevant for future OData sources.
**Key details:**
- Page with `$top=1000` (max per page) and `$skip=N*1000`
- Continue until response `value` array has fewer than `$top` records
- Multiple entity sets: `ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais`, `ExpectativasMercadoSelic`, `ExpectativasMercadoTop5Anuais`
- Filter format: `$filter=Indicador eq 'IPCA' and Data ge '2020-01-01'`

```python
async def _fetch_odata_paginated(
    self, entity_set: str, odata_filter: str
) -> list[dict]:
    """Fetch all pages from a BCB Focus OData endpoint."""
    all_records = []
    skip = 0
    page_size = 1000

    while True:
        params = {
            "$format": "json",
            "$top": str(page_size),
            "$skip": str(skip),
            "$filter": odata_filter,
            "$orderby": "Data desc",
        }
        url = f"/olinda/servico/Expectativas/versao/v1/odata/{entity_set}"
        response = await self._request("GET", url, params=params)
        data = response.json()
        items = data.get("value", [])
        all_records.extend(items)

        if len(items) < page_size:
            break  # Last page
        skip += page_size

    return all_records
```

### Pattern 3: Bulk CSV Download for CFTC COT
**What:** Download yearly ZIP files containing disaggregated COT reports as large CSVs, parse with pandas, extract net positions for tracked contracts.
**When to use:** CFTC COT connector (CONN-08). Historical data comes as `fut_disagg_txt_{YYYY}.zip`.
**Key details:**
- ZIP files contain a single CSV with 200+ columns
- Filter by `CFTC_Contract_Market_Code` to select tracked contracts
- Compute net positions: `Long - Short` for each of 4 categories (Producer, Swap Dealer, Managed Money, Other Reportable)
- Current week data available at `publicreporting.cftc.gov/resource/72hh-3qpy.csv` via Socrata SODA API

```python
async def _download_historical_year(self, year: int) -> pd.DataFrame:
    """Download and parse one year of CFTC disaggregated data."""
    url = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
    response = await self._request("GET", url)

    import zipfile
    import io

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as f:
            df = pd.read_csv(f)

    # Filter for tracked contracts
    df = df[df["CFTC_Contract_Market_Code"].isin(self.CONTRACT_CODES.values())]
    return df
```

### Pattern 4: Treasury.gov CSV Yield Curve Parsing
**What:** Download year-by-year CSV files from Treasury.gov containing daily yield curve data with fixed tenor columns.
**When to use:** US Treasury connector (CONN-09).
**Key details:**
- Nominal curve: `type=daily_treasury_yield_curve`
- Real (TIPS) curve: `type=daily_treasury_real_yield_curve`
- CSV columns: Date, 1 Mo, 2 Mo, 3 Mo, 4 Mo, 6 Mo, 1 Yr, 2 Yr, 3 Yr, 5 Yr, 7 Yr, 10 Yr, 20 Yr, 30 Yr
- New as of Feb 2025: 1.5-month tenor added
- Breakeven = Nominal - Real at matching tenors (5Y, 7Y, 10Y, 20Y, 30Y)

```python
TENOR_MAP = {
    "1 Mo": ("1M", 30), "2 Mo": ("2M", 60), "3 Mo": ("3M", 90),
    "4 Mo": ("4M", 120), "6 Mo": ("6M", 180), "1 Yr": ("1Y", 365),
    "2 Yr": ("2Y", 730), "3 Yr": ("3Y", 1095), "5 Yr": ("5Y", 1825),
    "7 Yr": ("7Y", 2555), "10 Yr": ("10Y", 3650), "20 Yr": ("20Y", 7300),
    "30 Yr": ("30Y", 10950),
}
```

### Pattern 5: IBGE SIDRA Path-Based API
**What:** The IBGE SIDRA API uses a unique path-based parameter format (not query params) where filters are encoded as path segments.
**When to use:** IBGE SIDRA connector (CONN-06).
**Key details:**
- Base URL: `https://apisidra.ibge.gov.br/values`
- Parameters encoded in path: `/t/7060/n1/all/v/63/p/{period}/c315/{group_codes}`
- First row of response is a header row (must be skipped)
- Period format: `YYYYMM` (e.g., `202401`)
- Response fields: `D3C` (period code), `D4C` (classification code), `V` (value)

```python
async def fetch_ipca_components(
    self, start_period: str, end_period: str, variable: int = 63
) -> list[dict]:
    group_codes = ",".join(str(code) for code in self.IPCA_GROUPS.values())
    url = (
        f"/values/t/7060/n1/all/v/{variable}"
        f"/p/{start_period}-{end_period}"
        f"/c315/{group_codes}"
    )
    response = await self._request("GET", url)
    data = response.json()
    # Skip header row (first element)
    return data[1:] if len(data) > 1 else []
```

### Pattern 6: Store to Different Target Tables
**What:** Phase 3 connectors write to four different target tables, unlike Phase 2 which only wrote to `macro_series` and `market_data`.
**When to use:** Each connector chooses its target table based on data type.

| Connector | Target Table | Model Class | Natural Key Constraint |
|-----------|-------------|-------------|----------------------|
| BCB Focus | `macro_series` | `MacroSeries` | `uq_macro_series_natural_key` (series_id, observation_date, revision_number) |
| B3/Tesouro Direto | `curves` | `CurveData` | `uq_curves_natural_key` (curve_id, curve_date, tenor_days) |
| IBGE SIDRA | `macro_series` | `MacroSeries` | `uq_macro_series_natural_key` |
| STN Fiscal | `fiscal_data` | `FiscalData` | `uq_fiscal_data_natural_key` (series_id, observation_date, fiscal_metric) |
| CFTC COT | `flow_data` | `FlowData` | `uq_flow_data_natural_key` (series_id, observation_date, flow_type) |
| US Treasury | `curves` | `CurveData` | `uq_curves_natural_key` |
| BCB FX Flow | `flow_data` | `FlowData` | `uq_flow_data_natural_key` |

### Anti-Patterns to Avoid
- **Inheriting BcbSgsConnector for BCB-sourced connectors:** BCB FX Flow and DI swap curve use the same API but target different tables. Inherit from BaseConnector directly to keep each connector self-contained.
- **Storing BCB Focus raw JSON without structuring by horizon:** Each Focus expectation must be mapped to a distinct `series_id` encoding the indicator and reference year/period (e.g., `BR_FOCUS_IPCA_2026_MEDIAN`). Dumping raw JSON loses this structure.
- **Downloading CFTC ZIP files for current week:** Use the Socrata CSV API (`publicreporting.cftc.gov`) for the latest report; only use ZIP files for historical backfill.
- **Blocking the event loop with pandas CSV parsing:** Large CFTC CSV files should be parsed with `await asyncio.to_thread(pd.read_csv, ...)` to keep the event loop responsive.
- **Hardcoding Treasury.gov CSV column names:** Treasury.gov added a 1.5-month tenor in Feb 2025. Parse columns dynamically using the TENOR_MAP pattern; skip unknown columns gracefully.
- **Ignoring Tesouro Direto JSON endpoint instability:** The `treasurybondsinfo.json` endpoint has been reported as intermittently 404/403 in 2025. Implement a CSV fallback via the downloadable CSV files from the Tesouro Direto website.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OData pagination | Custom cursor logic | Loop with `$top`/`$skip` until len(items) < page_size | OData protocol standard; BCB Focus uses standard implementation |
| ZIP file extraction | Shell commands / temp files | stdlib `zipfile.ZipFile(io.BytesIO(content))` | In-memory extraction, no temp files, cleanup-free |
| CFTC CSV parsing | Manual line splitting | `pd.read_csv()` with dtype specification | 200+ columns, handles quoting/escaping edge cases |
| Treasury CSV parsing | Custom parser | `pd.read_csv()` or `csv.DictReader` | Clean CSV format, standard header row |
| Breakeven curve computation | Manual per-tenor math | Simple dict comprehension: `nominal[tenor] - real[tenor]` | Straightforward subtraction at matching tenors |
| BCB Focus series_id generation | Manual string building | f-string pattern: `f"BR_FOCUS_{indicator}_{year}_MEDIAN"` | Consistent naming convention across all Focus series |

**Key insight:** The extended connectors are primarily integration work -- correctly calling external APIs, parsing their responses, and mapping them to the existing database schema. The BaseConnector ABC, `_bulk_insert`, and `_ensure_data_source`/`_ensure_series_metadata` patterns from Phase 2 handle 80% of the work. The complexity is in the diversity of API formats, not algorithmic difficulty.

## Common Pitfalls

### Pitfall 1: BCB Focus OData Pagination Termination
**What goes wrong:** Infinite loop if pagination termination condition is wrong. The API returns an empty `value` array (not a 404) when all data is consumed.
**Why it happens:** Not all OData implementations follow the same pagination semantics.
**How to avoid:** Terminate when `len(items) < $top` (i.e., last page is partial or empty). Add a safety maximum iteration count (e.g., 100 pages = 100K records).
**Warning signs:** Connector hangs or makes excessive API calls.

### Pitfall 2: BCB Focus Series ID Disambiguation by Horizon
**What goes wrong:** Focus expectations for different reference years (2025, 2026, 2027) get mixed into the same `series_id`, destroying the horizon structure.
**Why it happens:** Focus returns `DataReferencia` (the forecast target year/month) as a separate field. If the series_id only encodes the indicator (`BR_FOCUS_IPCA_MEDIAN`), all horizons collapse together.
**How to avoid:** Encode the reference year in the series_id: `BR_FOCUS_IPCA_2026_MEDIAN`. For monthly expectations, use `BR_FOCUS_IPCA_202601_MEDIAN`. The `observation_date` column stores the publication date (survey date), while the reference year is embedded in the series key.
**Warning signs:** Duplicate key violations on `macro_series` for Focus data with the same publication date.

### Pitfall 3: IBGE SIDRA Response Format -- Header Row
**What goes wrong:** First row of SIDRA API response is a metadata/header row, not data. Parsing it as data produces garbage records.
**Why it happens:** SIDRA API returns the column descriptions as the first array element.
**How to avoid:** Always skip `data[0]` and process `data[1:]`. Validate that the first element has string-type values in numeric fields.
**Warning signs:** Records with None/empty values or string errors on float conversion.

### Pitfall 4: IBGE SIDRA Period Format
**What goes wrong:** SIDRA uses `YYYYMM` period format (e.g., `202401`), not dates. Converting to a date for `observation_date` requires choosing a day-of-month convention.
**Why it happens:** Monthly macro data does not have a specific day -- it represents the whole month.
**How to avoid:** Use the first day of the month as the observation_date: `date(year, month, 1)`. This is consistent with how BCB SGS and FRED handle monthly series.
**Warning signs:** Date parsing errors when treating `202401` as a date string.

### Pitfall 5: CFTC Contract Code Mismatch
**What goes wrong:** CFTC contract codes change or have multiple variants. The disaggregated report uses `CFTC_Contract_Market_Code` which may differ from the legacy COT code.
**Why it happens:** The CFTC has multiple report formats (legacy, disaggregated, TFF) with different column names.
**How to avoid:** Use the disaggregated report columns consistently: `CFTC_Contract_Market_Code` for filtering, and the `_Positions_Long_All` / `_Positions_Short_All` pattern for position extraction. Verify contract codes against actual CSV headers.
**Warning signs:** Empty DataFrames after filtering by contract code.

### Pitfall 6: CFTC CSV Column Names with Spaces and Long Names
**What goes wrong:** CFTC disaggregated CSV has column names like `Prod_Merc_Positions_Long_All`, `Swap_Positions_Long_All`, `M_Money_Positions_Long_All`, `Other_Rept_Positions_Long_All`. These are easily mistyped.
**Why it happens:** CFTC uses verbose, inconsistent naming conventions.
**How to avoid:** Define column name constants at class level. Validate column existence before access. Use pandas column selection with explicit names.
**Warning signs:** KeyError on DataFrame column access.

### Pitfall 7: Treasury.gov CSV Empty Cells and N/A Values
**What goes wrong:** Treasury yield CSV contains empty cells and "N/A" strings for tenors that were not yet issued or temporarily missing.
**Why it happens:** Not all yield tenors are available for all dates (e.g., 4-month bill only started recently; 1.5-month started Feb 2025).
**How to avoid:** Treat empty strings and "N/A" as missing. Skip records where rate is None. Do not assume all tenors exist on all dates.
**Warning signs:** ValueError when parsing "N/A" as float.

### Pitfall 8: Tesouro Direto JSON Endpoint Instability
**What goes wrong:** The `treasurybondsinfo.json` endpoint returns 404 or 403 errors intermittently.
**Why it happens:** Tesouro Direto website has been unstable; endpoint may block non-browser requests via User-Agent detection.
**How to avoid:** Set a browser-like User-Agent header. Implement a fallback to CSV download URLs. Consider using NTN-B rates derived from BCB SGS if JSON endpoint is permanently unavailable. The CSV files from `tesourodireto.com.br/titulos/historico-de-precos-e-taxas.htm` provide the same data.
**Warning signs:** Repeated 403/404 responses from Tesouro Direto.

### Pitfall 9: Tesouro Transparente API for STN Fiscal
**What goes wrong:** The `apidatalake.tesouro.gov.br` endpoints may not provide the expected data format or may be slow/unreliable.
**Why it happens:** Tesouro Transparente is a data lake with various endpoints that may change.
**How to avoid:** Use BCB SGS fiscal series as the primary source (series 5364, 21864, 21865, 7620) -- they are reliable and follow the established pattern. Use Tesouro Transparente only for debt composition data that is not available from BCB SGS. Gracefully handle Tesouro Transparente failures without blocking the connector.
**Warning signs:** Timeout or unexpected JSON format from apidatalake.tesouro.gov.br.

### Pitfall 10: DI Swap Curve Rate Conversion
**What goes wrong:** BCB SGS DI swap series (#7805-7816) return rates as percentages (e.g., `13.50` meaning 13.50% per year). Storing without conversion breaks downstream curve analytics that expect decimal rates.
**Why it happens:** BCB publishes rates in percentage format.
**How to avoid:** Divide by 100 when storing to the `curves` table: `rate = value / 100.0`. Document the convention in the connector docstring. The CurveData model's `rate` column should store decimal format (0.1350 = 13.50%).
**Warning signs:** Unreasonable rate values in `curves` table (e.g., 13.50 instead of 0.1350).

## Code Examples

Verified patterns from official sources and established Phase 2 codebase:

### BCB Focus OData Fetch with Pagination
```python
# Source: BCB Open Data Portal - Expectativas OData API
# URL: https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/swagger-ui3

FOCUS_INDICATORS = ["IPCA", "Selic", "PIB", "Câmbio", "IGP-M"]

async def fetch_annual_expectations(
    self, indicator: str, start_date: date, end_date: date
) -> list[dict[str, Any]]:
    """Fetch annual expectations for a given macro indicator."""
    odata_filter = (
        f"Indicador eq '{indicator}' "
        f"and Data ge '{start_date.strftime('%Y-%m-%d')}' "
        f"and Data le '{end_date.strftime('%Y-%m-%d')}'"
    )
    raw_items = await self._fetch_odata_paginated(
        "ExpectativasMercadoAnuais", odata_filter
    )

    records = []
    for item in raw_items:
        survey_date = datetime.strptime(item["Data"], "%Y-%m-%d").date()
        ref_year = item["DataReferencia"]  # e.g., "2026"
        series_key = f"BR_FOCUS_{indicator.upper()}_{ref_year}_MEDIAN"

        records.append({
            "_series_key": series_key,
            "observation_date": survey_date,
            "value": item["Mediana"],
            "release_time": datetime.combine(
                survey_date, datetime.min.time()
            ).replace(tzinfo=ZoneInfo("America/Sao_Paulo")),
            "revision_number": 0,
            "source": self.SOURCE_NAME,
        })

    return records
```

### DI Swap Curve from BCB SGS
```python
# Source: BCB SGS API - DI swap series 7805-7816
# Each series represents a fixed tenor of the DI pre curve

DI_SWAP_REGISTRY = {
    "DI_SWAP_30D":  (7805, "1M",  30),
    "DI_SWAP_60D":  (7806, "2M",  60),
    "DI_SWAP_90D":  (7807, "3M",  90),
    "DI_SWAP_120D": (7808, "4M",  120),
    "DI_SWAP_150D": (7809, "5M",  150),
    "DI_SWAP_180D": (7810, "6M",  180),
    "DI_SWAP_210D": (7811, "7M",  210),
    "DI_SWAP_240D": (7812, "8M",  240),
    "DI_SWAP_270D": (7813, "9M",  270),
    "DI_SWAP_300D": (7814, "10M", 300),
    "DI_SWAP_330D": (7815, "11M", 330),
    "DI_SWAP_360D": (7816, "12M", 360),
}

# Each observation produces a CurveData record:
{
    "curve_id": "DI_PRE",
    "curve_date": obs_date,           # from BCB SGS response
    "tenor_days": 30,                 # from registry
    "tenor_label": "1M",             # from registry
    "rate": value / 100.0,           # Convert percentage to decimal
    "curve_type": "swap",
    "source": "BCB_SGS",
}
```

### CFTC COT Net Position Computation
```python
# Source: CFTC Disaggregated Futures Only Report
# URL: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm

# Column name patterns in disaggregated report:
CATEGORIES = {
    "DEALER":    ("Dealer_Positions_Long_All",    "Dealer_Positions_Short_All"),
    "ASSETMGR":  ("Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All"),
    "LEVERAGED": ("Lev_Money_Positions_Long_All",  "Lev_Money_Positions_Short_All"),
    "OTHER":     ("Other_Rept_Positions_Long_All", "Other_Rept_Positions_Short_All"),
}

def compute_net_positions(self, df: pd.DataFrame) -> list[dict]:
    """Compute net positions for each contract x category."""
    records = []
    for _, row in df.iterrows():
        report_date = pd.to_datetime(row["Report_Date_as_YYYY-MM-DD"]).date()
        contract_code = row["CFTC_Contract_Market_Code"]
        contract_name = self._reverse_contract_map.get(contract_code)
        if contract_name is None:
            continue

        for cat_name, (long_col, short_col) in self.CATEGORIES.items():
            net = row[long_col] - row[short_col]
            series_key = f"CFTC_{contract_name}_{cat_name}_NET"

            records.append({
                "_series_key": series_key,
                "observation_date": report_date,
                "value": float(net),
                "flow_type": f"CFTC_{cat_name}_NET",
                "unit": "contracts",
                "release_time": None,  # CFTC publishes Fridays
            })

    return records
```

### US Treasury Yield Curve CSV Parsing
```python
# Source: US Treasury Daily Rates CSV
# URL: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/

NOMINAL_URL_TEMPLATE = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/daily-treasury-rates.csv/all/{year}"
    "?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)

async def fetch_nominal_curve(self, year: int) -> list[dict]:
    url = self.NOMINAL_URL_TEMPLATE.format(year=year)
    response = await self._request("GET", url)

    df = await asyncio.to_thread(
        pd.read_csv, io.StringIO(response.text)
    )

    records = []
    for _, row in df.iterrows():
        curve_date = pd.to_datetime(row["Date"]).date()

        for csv_col, (tenor_label, tenor_days) in self.TENOR_MAP.items():
            rate_val = row.get(csv_col)
            if pd.isna(rate_val) or rate_val == "N/A":
                continue

            records.append({
                "curve_id": "UST_NOM",
                "curve_date": curve_date,
                "tenor_days": tenor_days,
                "tenor_label": tenor_label,
                "rate": float(rate_val) / 100.0,  # % to decimal
                "curve_type": "sovereign_nominal",
                "source": "TREASURY_GOV",
            })

    return records
```

### IBGE SIDRA IPCA Component Fetch
```python
# Source: IBGE SIDRA API - Table 7060 (IPCA)
# URL: https://apisidra.ibge.gov.br/values/t/7060/...

IPCA_GROUPS = {
    "FOOD":          7169,
    "HOUSING":       7170,
    "HOUSEHOLD":     7445,
    "CLOTHING":      7171,
    "TRANSPORT":     7432,
    "HEALTH":        7172,
    "PERSONAL":      7173,
    "EDUCATION":     7174,
    "COMMUNICATION": 7175,
}

async def fetch_ipca_by_group(self, start_period: str, end_period: str):
    group_codes = ",".join(str(c) for c in self.IPCA_GROUPS.values())
    url = (
        f"/values/t/7060/n1/all/v/63"
        f"/p/{start_period}-{end_period}"
        f"/c315/{group_codes}"
    )
    # Note: BASE_URL = "https://apisidra.ibge.gov.br"
    response = await self._request("GET", url)
    data = response.json()

    records = []
    for item in data[1:]:  # Skip header row
        period = item["D3C"]  # "202401"
        group_code = int(item["D4C"])
        value_str = item["V"]

        if value_str in ("", "-", "..."):
            continue

        obs_date = date(int(period[:4]), int(period[4:6]), 1)
        group_name = self._code_to_name.get(group_code)

        records.append({
            "_series_key": f"BR_IPCA_{group_name}_MOM",
            "observation_date": obs_date,
            "value": float(value_str),
            "release_time": datetime.now(tz=ZoneInfo("America/Sao_Paulo")),
            "revision_number": 0,
            "source": "IBGE_SIDRA",
        })

    return records
```

### Respx Mocking Pattern for Phase 3 Tests
```python
# Following the established pattern from test_bcb_sgs.py

@pytest.mark.asyncio
async def test_bcb_focus_annual_expectations():
    """Verify BCB Focus connector parses annual expectation data."""
    mock_response = {
        "value": [
            {
                "Indicador": "IPCA",
                "Data": "2025-01-06",
                "DataReferencia": "2026",
                "Mediana": 4.50,
                "Media": 4.52,
                "DesvioPadrao": 0.30,
                "Minimo": 3.20,
                "Maximo": 6.10,
                "numeroRespondentes": 95,
            }
        ]
    }

    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(
            url__contains="ExpectativasMercadoAnuais"
        ).respond(200, json=mock_response)

        async with BcbFocusConnector() as conn:
            records = await conn.fetch_annual_expectations(
                indicator="IPCA",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    assert len(records) == 1
    assert records[0]["_series_key"] == "BR_FOCUS_IPCA_2026_MEDIAN"
    assert records[0]["value"] == pytest.approx(4.50)
    assert records[0]["observation_date"] == date(2025, 1, 6)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CFTC bulk text files only | CFTC Socrata API + bulk ZIP | 2020+ | Socrata allows filtered queries for current data without downloading full ZIPs |
| Treasury XML feed | Treasury CSV download | Both available | CSV is simpler to parse; XML provides same data with different structure |
| Tesouro Direto single JSON endpoint | Tesouro Direto JSON + CSV fallback | 2025 instability | JSON endpoint (`treasurybondsinfo.json`) reported intermittently unavailable; CSV files remain stable |
| BCB Focus without OData pagination | BCB Focus OData with `$top`/`$skip` | Standard | Large result sets require pagination; 1000 records per page limit |
| IBGE SIDRA old API | IBGE SIDRA API v3 | Current | Path-based parameter format, JSON response, header row in response |
| Treasury monotone convex yield curve | MC spline method | Dec 2021 | Treasury changed curve fitting methodology; data format unchanged |
| CFTC old report format | CFTC disaggregated with 4 trader categories | Sep 2009 | Disaggregated report provides more granular positioning than legacy 2-category report |
| Treasury 13 tenors | Treasury 14+ tenors | Feb 2025 | 1.5-month (6-week) bill benchmark added; connector must handle dynamic columns |

**Deprecated/outdated:**
- **CFTC legacy COT report (2 categories):** Use disaggregated report (4 categories: Producer, Swap Dealer, Managed Money, Other Reportable) for richer positioning data.
- **Tesouro Direto old JSON URL patterns:** The `treasurebond/all` endpoint may not work; use `treasurybondsinfo.json` or CSV fallback.
- **CFTC text files from `cftc.gov/dea/newcot/`:** These are current-week only. Use yearly ZIP archives for historical data plus Socrata API for current week.

## Open Questions

1. **Tesouro Direto JSON Endpoint Availability**
   - What we know: The `treasurybondsinfo.json` endpoint has been reported as intermittently returning 404/403 errors in 2025. It may require a browser-like User-Agent header.
   - What's unclear: Whether the endpoint is permanently unreliable or just requires specific headers. The CSV download URLs appear more stable.
   - Recommendation: Implement JSON endpoint as primary with a User-Agent header (`Mozilla/5.0`). Implement CSV download as fallback. If JSON is consistently unavailable during testing, switch to CSV-only. For NTN-B real rates, BCB SGS does not provide a direct series, so Tesouro Direto is the required source.

2. **Tesouro Transparente API Reliability for Debt Composition**
   - What we know: The `apidatalake.tesouro.gov.br` API exists but documentation is sparse. The SADIPEM endpoint is documented but focuses on municipal debt.
   - What's unclear: Whether the API provides the specific debt composition breakdown (Selic-indexed %, IPCA-indexed %, pre-fixed %, FX-indexed %) needed for the fiscal connector.
   - Recommendation: Start with BCB SGS fiscal series as the primary data source (these are reliable). Explore Tesouro Transparente for debt composition during implementation. If unavailable, compute debt composition from BCB SGS series or defer to Phase 4. Do not let Tesouro Transparente instability block the STN Fiscal connector.

3. **CFTC Disaggregated Report Column Names**
   - What we know: CFTC column names for the disaggregated report include patterns like `Prod_Merc_Positions_Long_All`, `Swap__Positions_Long_All` (note double underscore), `M_Money_Positions_Long_All`, `Other_Rept_Positions_Long_All`. However, the Socrata API may use different column names than the ZIP CSV.
   - What's unclear: Whether column names are consistent across years and between the bulk ZIP and the Socrata API export.
   - Recommendation: Download a sample ZIP file and a sample Socrata CSV during implementation to verify column names. Define column name constants as class-level attributes and validate their existence at parse time. Log warnings for missing columns rather than crashing.

4. **BCB Focus Entity Set Names**
   - What we know: The BCB Expectativas OData API has multiple entity sets including `ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais` (note: singular `Expectativa` without the 's'), `ExpectativasMercadoSelic`, `ExpectativasMercadoTop5Anuais`, and `ExpectativasMercadoInflacao24Meses`.
   - What's unclear: The exact entity set name for each endpoint (some may be plural, some singular). The Swagger documentation at the BCB portal should be consulted.
   - Recommendation: Verify entity set names against the Swagger UI at `https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/swagger-ui3`. Log the actual URL and response on first successful call. Handle 404 errors gracefully with clear error messages naming the entity set.

5. **IBGE SIDRA API Rate Limiting**
   - What we know: IBGE SIDRA has no documented rate limit, but conservative usage recommends 2 seconds between requests.
   - What's unclear: Whether bulk requests (all 9 groups in one URL) count as one request or are rate-limited differently.
   - Recommendation: Fetch all 9 IPCA groups in a single request (they can be comma-separated in the URL path). This minimizes API calls. If the API returns errors, add 2-second delays between retries.

## Sources

### Primary (HIGH confidence)
- BCB Open Data Portal - Focus Expectativas OData API: https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado (endpoint structure, entity sets, filter syntax)
- BCB Focus Swagger documentation: https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/swagger-ui3 (endpoint names, parameter formats)
- IBGE SIDRA API documentation: https://servicodados.ibge.gov.br/api/docs/agregados?versao=3 (path-based API format, response structure)
- IBGE SIDRA Table 7060: https://sidra.ibge.gov.br/tabela/7060 (IPCA groups, classification codes)
- CFTC Historical Compressed Reports: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm (ZIP file URL pattern, disaggregated report format)
- CFTC Socrata API: https://publicreporting.cftc.gov/resource/72hh-3qpy.csv (disaggregated futures only, filterable)
- US Treasury Daily Rates: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve (CSV format, tenor columns)
- US Treasury XML Feed API: https://home.treasury.gov/treasury-daily-interest-rate-xml-feed (alternative to CSV)
- Existing codebase: `src/connectors/base.py`, `src/connectors/bcb_sgs.py`, `src/connectors/bcb_ptax.py`, `src/connectors/fred.py` (established patterns)
- Existing models: `src/core/models/curves.py`, `src/core/models/fiscal_data.py`, `src/core/models/flow_data.py`, `src/core/models/macro_series.py` (target table schemas)

### Secondary (MEDIUM confidence)
- Tesouro Direto JSON endpoint: `https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/service/api/treasurybondsinfo.json` (reported instability in 2025, confirmed by multiple sources)
- Tesouro Transparente API: https://www.gov.br/tesouronacional/pt-br/central-de-conteudo/apis (SADIPEM documentation, debt composition endpoints unclear)
- BCB SGS series 7805-7816 for DI swap curve: verified via BCB SGS portal and Fase0 guide documentation
- BCB SGS series 22704, 22705, 22706, 12070 for FX flow: verified via BCB Open Data Portal
- CFTC disaggregated report column names: verified via `cot_reports` Python library documentation and CFTC historical file samples
- Treasury 1.5-month tenor addition: confirmed per US Treasury daily rates page (started Feb 18, 2025)

### Tertiary (LOW confidence)
- Tesouro Transparente debt composition specific endpoint format: needs validation during implementation
- CFTC Socrata API column name consistency with ZIP CSV column names: needs validation with sample data
- BCB Focus entity set names (singular vs. plural): needs validation against Swagger UI

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use from Phase 2; no new dependencies needed
- Architecture: HIGH - all patterns directly extend established Phase 2 patterns (BaseConnector, _bulk_insert, respx mocking)
- API endpoints: HIGH for BCB Focus, IBGE SIDRA, CFTC, Treasury.gov (well-documented, verified); MEDIUM for Tesouro Direto JSON (instability reported)
- Database mapping: HIGH - all target models (CurveData, FiscalData, FlowData, MacroSeries) already exist with correct natural key constraints
- Pitfalls: HIGH - documented from official API documentation, established patterns, and web research

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days - stable APIs; Tesouro Direto endpoint should be re-verified)
