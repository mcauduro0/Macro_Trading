# Pitfalls Research

**Domain:** Macro Trading Data Infrastructure
**Researched:** 2026-02-19
**Confidence:** HIGH (domain-specific pitfalls well-documented across multiple authoritative sources)

## Critical Pitfalls

These are mistakes that cause data corruption, silent signal degradation, or full rewrites.

### Pitfall 1: Look-Ahead Bias from Missing Point-in-Time Discipline

**What goes wrong:**
The pipeline stores only the latest revised value for macroeconomic series (GDP, NFP, CPI). When signals or backtests consume this data, they use information that was not available at the time of the trading decision. GDP Q1 2014 was first released at 17,149.6, revised to 17,101.3 a month later, then revised again to 17,016.0. A naive `get_series()` call returns only the final revision. Any signal built on this data is cheating -- it "knew" the revised number before the market did.

**Why it happens:**
Most free APIs (FRED `get_series`, BCB SGS) return only the current value by default. Developers fetch and store data without realizing they are overwriting the original release with a revision. The pipeline "works" but the data is silently wrong for any temporal analysis.

**How to avoid:**
- Use ALFRED vintage dates via `fredapi.get_series_all_releases()` or `get_series_first_release()` for every revisable series.
- Design the schema with three date columns per observation: `observation_date`, `release_date` (when this value was first published), and `vintage_date` (which snapshot of reality this belongs to).
- Store every revision as a separate row, not an UPDATE to the existing row.
- For BCB SGS series that lack vintage tracking, record `ingestion_timestamp` as a proxy for "known-since" and never overwrite.
- Build a `get_as_of(series, as_of_date)` query function that returns only data known at a given point in time. This is the only function signal generation code should call.

**Warning signs:**
- Backtest results that are "too good" -- especially on macro signals using GDP, employment, or inflation data.
- No `release_date` or `vintage_date` column in the schema.
- UPDATE statements in the ingestion pipeline for revisable series.
- Downstream code calling `SELECT * WHERE observation_date <= X` without filtering on `release_date <= X`.

**Phase to address:**
Phase 1 (Schema Design). This must be in the foundational schema. Retrofitting point-in-time correctness requires reingesting all data with vintage information, which is effectively a rewrite.

**Confidence:** HIGH -- This is the most documented pitfall in quantitative macro research. CEIC, Macrosynergy/JPMaQS, and the Philadelphia Fed Real-Time Data Set all exist specifically because this problem destroyed research results at scale.

---

### Pitfall 2: Free API Fragility Causing Silent Data Gaps

**What goes wrong:**
The pipeline depends on 200+ series from free APIs (Yahoo Finance/yfinance, BCB SGS, FRED, CFTC, IBGE). These APIs break without warning. Yahoo Finance has no official API -- yfinance is a web scraper that fails with 429 errors when Yahoo changes rate limits (documented crackdown in late 2024, ongoing in 2025). BCB SGS can be slow or unresponsive under load. CFTC changes CSV formats without notice (documented format break in June 2015 that broke automated parsers). The pipeline runs, returns partial data, and nobody notices the gap until a signal produces garbage weeks later.

**Why it happens:**
Free APIs have no SLA, no deprecation notice, and no obligation to maintain backward compatibility. Developers build pipelines that assume APIs always return data, and treat HTTP 200 with partial/empty results as success.

**How to avoid:**
- Implement per-source health checks that verify: (a) expected number of observations returned, (b) latest observation is within expected staleness window, (c) values are within reasonable bounds (not all zeros, not all NaN).
- Build a `data_quality_log` table that records every ingestion run: source, series_id, rows_fetched, rows_expected, latency_ms, http_status, error_message.
- Set up alerting when any series goes stale beyond its expected publication frequency (e.g., FRED monthly series not updated in 35 days).
- For Yahoo Finance specifically: cache aggressively, implement exponential backoff, and have a fallback source (EODHD, Finnhub) for critical price series.
- For CFTC: use the official Public Reporting Environment API (launched Oct 2022) or historical compressed files rather than scraping HTML pages. Use community libraries (`cot_reports`, `pycot-reports`) that handle format changes.
- For BCB SGS: use `python-bcb` which handles caching and date format conversion, rather than raw HTTP calls.

**Warning signs:**
- No monitoring dashboard showing per-source ingestion success rates.
- Series with unexplained gaps in the time dimension (missing weeks/months).
- Ingestion logs that only record success/failure, not row counts.
- Pipeline returns empty DataFrame without raising an error.

**Phase to address:**
Phase 2 (Ingestion Layer). Build the monitoring and health-check infrastructure alongside the first collectors, not after.

**Confidence:** HIGH -- yfinance rate-limiting issues are extensively documented on GitHub (issues #2125, #2128, #2422). CFTC format changes are documented in their Historical Special Announcements. BCB SGS fragility confirmed by multiple community library authors.

---

### Pitfall 3: Brazilian Data Format Misinterpretation

**What goes wrong:**
Brazilian financial data uses comma as decimal separator (`1.234,56` means one thousand two hundred thirty-four point five six), DD/MM/YYYY date format, and PTAX exchange rates with MM-DD-YYYY in some BCB endpoints. A parser that treats `01/02/2024` as January 2nd (US format) when it actually means February 1st (Brazilian format) produces silently wrong data. A parser that treats `1.234` as 1.234 (US) when it actually means 1234 (Brazilian thousands separator) produces values off by ~1000x.

**Why it happens:**
Python's `pandas.read_csv()` defaults to US locale conventions. When ingesting from BCB, IBGE, ANBIMA, or B3 sources, the data arrives in Brazilian format but gets parsed with default settings. The error is silent because `1.234` is a valid float in both conventions -- just with different meanings.

**How to avoid:**
- Create a `BrazilianDataParser` utility that enforces `decimal=','` and `thousands='.'` for all BR sources.
- For date parsing, use explicit format strings (`%d/%m/%Y` for BCB SGS, `%d-%m-%Y` for some ANBIMA files) -- never rely on `pd.to_datetime()` with `infer_datetime_format=True`.
- Use the PYield library's approach: the first non-null string determines the format for the entire collection, with explicit DD-MM-YYYY vs YYYY-MM-DD disambiguation.
- Tag every data source in a registry with its locale (`pt_BR` vs `en_US`) and date format, so parsers automatically select the correct convention.
- Write explicit round-trip tests: ingest a known Brazilian-format file, parse it, and assert that `1.234,56` becomes `1234.56` and `01/02/2024` becomes `2024-02-01`.

**Warning signs:**
- Yield values that are exactly 1000x too large or too small.
- Date series that have suspicious gaps on the 13th-31st of every month (dates that cannot be valid in MM/DD format get silently dropped or error).
- PTAX exchange rates that look like BRL is worth 5000x USD instead of ~5x.
- Tests that pass when run with US locale but fail with Brazilian locale.

**Phase to address:**
Phase 1 (Schema Design) and Phase 2 (Ingestion Layer). The locale registry belongs in the source metadata schema. The parsers must be correct from the first ingestion.

**Confidence:** HIGH -- PYield, python-bcb, and brasa libraries all explicitly address this. Brazilian date/number format confusion is a well-known localization trap.

---

### Pitfall 4: TimescaleDB Compression Destroying Backfill Capability

**What goes wrong:**
The team enables aggressive compression policies (e.g., compress after 7 days) on hypertables. Later, when a backfill from 2010 is needed -- or when a data revision arrives for a month-old GDP number -- the pipeline needs to UPDATE or INSERT into compressed chunks. In TimescaleDB versions before 2.11, this was impossible without manual decompression. Even in 2.16+, bulk modifications on compressed chunks require decompression, which can temporarily bloat disk usage by 10-14x and cause compression policy conflicts.

**Why it happens:**
Compression is presented as a "set and forget" optimization. Developers enable it for storage savings (up to 90%) without realizing it creates a tension with the revision-tracking and backfill requirements that are core to macro data infrastructure.

**How to avoid:**
- Use TimescaleDB 2.16+ which has 1000x faster DML on compressed data when filtering by `segmentby` columns.
- Set `segmentby` to the column used in WHERE clauses during backfill (e.g., `series_id`) and `orderby` to `time ASC` (not the default `DESC`).
- Set `compress_after` to a generous delay for revisable series: at least 90 days for monthly macro data (GDP revisions can come 3 months later), 30 days for weekly data.
- For the 2010 backfill specifically: run it BEFORE enabling compression policies. Ingest historical data first, verify it, then turn on compression.
- Leave 20-30% extra disk headroom to accommodate temporary decompression during bulk operations.
- Always disable compression policy before bulk decompression; re-enable after the operation completes.

**Warning signs:**
- Disk space alarms during backfill operations.
- Compression policies running concurrently with bulk INSERT/UPDATE jobs.
- `compress_after` set to less than the maximum revision delay for the series in that hypertable.
- Backfill jobs failing with "cannot modify compressed chunk" errors.

**Phase to address:**
Phase 1 (Schema Design) for `segmentby`/`orderby` configuration. Phase 3 (Backfill) for compression timing. The 2010 backfill must complete before compression policies are activated.

**Confidence:** HIGH -- TimescaleDB documentation explicitly warns about this. Bug reports (#6255, #7502) document real-world compression policy failures.

---

### Pitfall 5: Curve Construction from Proxy Data Without Acknowledging the Approximation

**What goes wrong:**
The project plans to construct a BRL interest rate curve (DI curve) from BCB swap rate series because Bloomberg DI futures data is not available for free. The developer treats the BCB swap series as a direct substitute for DI futures, applies naive linear interpolation between available tenors, and produces a "yield curve" that looks reasonable but has material pricing errors at interpolated maturities. Worse, the interpolation is decoupled from the bootstrap -- rates are interpolated first, then bootstrapped, producing inconsistent forward rates with discontinuities.

**Why it happens:**
BCB publishes Pre x DI swap rates at standard tenors (30, 60, 90, 180, 360 days, etc.) which look like they should map directly to a curve. But these are swap rates, not zero rates or forward rates. The mapping requires careful bootstrapping. The Hagan & West (2006) paper demonstrates that decoupling interpolation from bootstrapping is a fundamental error that produces arbitrage-free-violating curves.

**How to avoid:**
- Document explicitly that the curve is an approximation built from proxy data, not from exchange-traded DI futures. Store a `curve_source_type` metadata field (`proxy_bcb_swap` vs `exchange_di_futures`).
- Use monotone convex interpolation (following Hagan & West), which produces continuous forward rates and does not require routine manual adjustment of inputs. This is the method the US Treasury adopted in 2020 specifically to avoid proxy-data distortions.
- Integrate the interpolation into the bootstrap loop iteratively: guess initial zero rates, interpolate, bootstrap, repeat until convergence.
- Validate the constructed curve against ANBIMA's published indicative rates (available for the last 5 business days) as a sanity check.
- Use the PYield library or QuantLib's Brazilian conventions for business day counting (BUS/252) and ANBIMA holiday calendar.

**Warning signs:**
- Forward rates that are negative or have large discontinuities between tenors.
- Curve values that diverge materially from ANBIMA's published indicative rates.
- No documentation in the codebase about the proxy nature of the data source.
- Using `np.interp()` (linear interpolation) for yield curve construction.

**Phase to address:**
Phase 4 (Derived Data / Curve Construction). This is a later phase because it depends on the raw data pipeline being correct first, but it requires dedicated research and careful implementation.

**Confidence:** MEDIUM -- The general curve construction pitfalls are well-documented (Hagan & West, Quantifi). The specific BCB swap-to-DI-curve mapping is less documented in English-language sources and needs validation against ANBIMA indicative rates.

---

### Pitfall 6: Timezone and Business Calendar Misalignment Across Data Sources

**What goes wrong:**
The pipeline ingests data from US sources (FRED, CFTC -- Eastern Time), Brazilian sources (BCB, IBGE, ANBIMA -- Brasilia Time, UTC-3), and global market data (Yahoo Finance -- exchange-local times). Without rigorous timezone handling, a US NFP release at 8:30 AM ET on a Friday and a Brazilian IPCA release at 9:00 AM BRT on the same Friday end up with the same naive timestamp, but they are actually 2 hours apart. Worse, when the US observes DST (March-November) but Brazil does not (since 2019), the offset between the two shifts from 2 hours to 1 hour. Joining these series on date alone produces incorrect temporal alignment.

**Why it happens:**
Developers use `timestamp` (without timezone) in the database, or store dates without times. When both NFP and IPCA have `observation_date = 2024-03-08`, they appear simultaneous, but NFP was released at 13:30 UTC and IPCA at 12:00 UTC. For daily-frequency macro data this seems harmless, but for intraday signals or event studies, it breaks causality.

**How to avoid:**
- Use `TIMESTAMPTZ` (timestamp with timezone) exclusively in TimescaleDB. Never use naive `TIMESTAMP` or `DATE` for release times.
- Store all timestamps in UTC internally. Convert to local time only at the display layer.
- Maintain an explicit `release_timezone` column in the source metadata table (e.g., `America/New_York` for FRED, `America/Sao_Paulo` for BCB).
- Use IANA timezone identifiers, never hardcoded UTC offsets (Brazil abandoned DST in 2019, but historical data from before 2019 needs DST-aware conversion).
- Build a unified holiday calendar combining ANBIMA holidays (Brazilian financial calendar), NYSE holidays (US market calendar), and a union calendar for cross-market analysis. Use `anbima_calendar` for Brazil and `exchange_calendars` for US/global.
- For daily data, distinguish between `observation_date` (what period the data covers), `release_date` (when it became available), and `release_time` (exact UTC moment of availability, if known).

**Warning signs:**
- Using `TIMESTAMP` without `TZ` in the schema.
- Hardcoded UTC offsets like `- timedelta(hours=3)` instead of IANA timezone conversion.
- Cross-market joins that produce incorrect matches during DST transition weeks (mid-March, early November).
- Holiday mismatches: pipeline expects data on a day when the Brazilian market is closed (e.g., Carnival, Tiradentes) but the US market is open.

**Phase to address:**
Phase 1 (Schema Design) for column types and timezone metadata. Phase 2 (Ingestion Layer) for timezone conversion logic. Phase 3 (Backfill) for historical DST-aware conversion of pre-2019 Brazilian data.

**Confidence:** HIGH -- Multiple authoritative sources confirm UTC storage as non-negotiable for multi-market systems. Brazil's DST abolition in 2019 is a documented gotcha.

---

### Pitfall 7: Non-Idempotent Backfill Creating Duplicates or Data Loss

**What goes wrong:**
The backfill pipeline is designed to load data from 2010 to present. It runs, partially fails at 2015 due to an API timeout, and is restarted. Without idempotent design, the rerun either (a) creates duplicate rows for 2010-2015 data (INSERT without dedup), or (b) fails because of unique constraint violations, or (c) overwrites 2010-2015 data with potentially different values (if using DELETE-then-INSERT and the API returned different data on the second call due to a revision).

**Why it happens:**
Developers build the "happy path" first -- a loop that fetches date ranges and INSERTs them. Error handling and restart logic are added later (or never). The pipeline works on the first run but fails catastrophically on any subsequent run.

**How to avoid:**
- Use UPSERT (`INSERT ... ON CONFLICT DO UPDATE`) with a composite natural key: `(series_id, observation_date, vintage_date)`. This is idempotent by definition -- rerunning produces the same result.
- Make the pipeline accept explicit `--start-date` and `--end-date` parameters. Never use `datetime.now()` or hardcoded dates.
- Generate deterministic record IDs from content (hash of series_id + observation_date + vintage_date), not from auto-increment or random UUIDs.
- Log every backfill run in a `backfill_runs` audit table: `run_id`, `series_id`, `date_range`, `rows_upserted`, `rows_unchanged`, `started_at`, `completed_at`, `status`.
- Chunk the backfill by year or month, so a failure in 2018 data does not require re-ingesting 2010-2017.
- Run backfill against staging tables first, validate, then swap into production (or UPSERT into production from staging).

**Warning signs:**
- Row counts that change when the same backfill is run twice.
- Auto-incrementing primary keys in the time series tables (suggests INSERT-only, not UPSERT).
- No `backfill_runs` audit table.
- Pipeline that uses `datetime.now()` anywhere in the data path.
- No `--start-date`/`--end-date` parameters on the backfill CLI.

**Phase to address:**
Phase 2 (Ingestion Layer) for the UPSERT pattern. Phase 3 (Backfill) for the chunked execution and audit logging.

**Confidence:** HIGH -- Idempotent pipeline design is one of the most discussed topics in data engineering. Multiple authoritative guides (StartDataEngineering, ml4devs, KDnuggets) converge on the same UPSERT + audit + chunking pattern.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store only latest value (no revisions) | Simpler schema, less storage | All backtests have look-ahead bias; cannot answer "what was known when" | Never for revisable macro series (GDP, NFP, CPI). Acceptable for non-revisable series (market prices). |
| Use yfinance without fallback source | Fast to implement, zero cost | Pipeline breaks when Yahoo rate-limits; multi-day data gaps | Only during prototyping. Must have fallback before production. |
| Single `observation_date` column (no release_time) | Simpler schema | Cannot determine data availability timing; event studies impossible | Never for a system that will support AI agents or intraday signal generation. |
| Hardcoded series IDs throughout codebase | Quick iteration | Adding/renaming a series requires code changes in multiple files; no source-of-truth | Only in throwaway scripts. Production must use a series registry table. |
| Skip ANBIMA holiday calendar | Avoid a dependency | Business day calculations wrong for Brazilian instruments; curve construction off by 1-2 days regularly | Never for Brazilian fixed income. Acceptable if only trading US instruments. |
| Parse all dates with `pd.to_datetime(infer=True)` | Fewer lines of code | Silently misparses Brazilian DD/MM dates as MM/DD when day <= 12; produces wrong data that passes all sanity checks except on the 13th+ of the month | Never. Always use explicit format strings. |
| Linear interpolation for yield curves | Easy to implement | Discontinuous forward rates; arbitrage-violating curves; hedging strategies that are not intuitively reasonable | Acceptable for rough approximations in research notebooks. Never for production curves. |

## Integration Gotchas

Common mistakes when connecting to external data sources.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FRED API | Using `get_series()` which returns only latest revisions | Use `fredapi` with `get_series_all_releases()` or `get_series_first_release()` for revisable series; use ALFRED vintage dates |
| BCB SGS | Sending DD/MM/YYYY dates to `dataInicial`/`dataFinal` as MM/DD/YYYY | Use `python-bcb` which handles date format conversion; explicitly use `%d/%m/%Y` format |
| BCB PTAX | Treating buying rate and selling rate as interchangeable | PTAX has distinct bid/ask rates; use the correct one for your convention (selling rate is standard for most financial contracts) |
| Yahoo Finance (yfinance) | No rate limit handling; no fallback | Implement exponential backoff; cache responses locally; have EODHD or Finnhub as fallback; limit to ~300 requests/hour |
| CFTC COT | Scraping HTML pages instead of using the API | Use CFTC Public Reporting Environment API (since Oct 2022) or historical compressed CSV files; use `cot_reports` library |
| CFTC COT | Assuming contract names are stable | Contract names change over time; use `cftc_contract_market_code` as the stable identifier, not the text name |
| IBGE | Assuming data is available in English or ISO format | IBGE data uses Portuguese labels and Brazilian number/date formats; build explicit translation and parsing layers |
| ANBIMA | Trying to download historical indicative rates | ANBIMA only publishes the last 5 business days online; historical data requires subscription or reconstruction from BCB series |
| TimescaleDB | Enabling compression before backfill completes | Backfill all historical data first, verify integrity, then enable compression policies with appropriate delays |

## Performance Traps

Patterns that work at small scale but fail as the dataset grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No `segmentby` on compressed hypertables | Full-chunk decompression on every DML targeting a single series | Set `segmentby='series_id'` so operations on one series only touch that segment | When you have 200+ series and do targeted updates/inserts |
| Default chunk interval (7 days) for daily macro data | Thousands of nearly-empty chunks (1 row per day per series); slow query planning | Set `chunk_interval` to 1 year for daily macro data (200 series x 365 days = 73K rows/chunk, well within memory) | When chunk count exceeds ~1000 and query planning slows |
| No continuous aggregates for common queries | Repeated full-table scans for rolling averages, z-scores, percentile ranks | Define continuous aggregates for standard transforms (e.g., 20-day rolling mean, YoY change) | When signal generation queries take >1s and are called per-series |
| Fetching all 200+ series sequentially | Backfill takes days; daily ingestion takes hours | Use async I/O (`asyncio` + `aiohttp`) with per-source rate limiting; parallelize across sources, serialize within each source | When total series count exceeds ~50 and daily ingestion window is tight |
| Storing every API response as raw JSON blobs | "We'll parse it later" -- but querying JSON is slow and schema is implicit | Parse and validate at ingestion time; store structured data in typed columns; archive raw responses separately for debugging | When analytical queries must scan JSON instead of typed columns |
| No retention policy on raw/staging data | Staging tables grow unbounded; backup sizes balloon | Set retention policies on staging tables (30-90 days); archive to compressed cold storage | When staging data exceeds 100GB and backup windows stretch |

## Security Mistakes

Domain-specific security issues for a macro trading data platform.

| Mistake | Risk | Prevention |
|---------|------|------------|
| API keys stored in source code or environment variables without encryption | Keys for FRED, Yahoo, EODHD leaked in git history; unauthorized data access; API key revoked by provider | Use a secrets manager (e.g., `python-dotenv` + `.env` in `.gitignore` minimum; Vault or cloud KMS for production). Never commit `.env` files. |
| No authentication on the data API consumed by AI agents | Any process on the network can query the data platform; data exfiltration or injection possible | Require API key or JWT for all data access, even internal. AI agents get scoped read-only tokens. |
| Signal/strategy logic stored alongside data pipeline code | Data breach exposes proprietary trading signals, not just infrastructure | Separate data infrastructure repo from signal/strategy repo. Different access controls, different deployment pipelines. |
| CFTC/FRED data cached without access controls | Cached files on shared filesystem accessible to unauthorized users | Store cached data in a controlled location with appropriate file permissions; log access to audit table. |
| No audit trail on data modifications | Cannot prove data integrity for compliance; cannot detect if data was tampered with | Log every INSERT/UPDATE/DELETE with user/process identity, timestamp, and before/after values for critical series. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Data ingestion "works":** Often missing -- validation that the correct number of rows was ingested; bounds checking on values; staleness alerting. Verify: run ingestion for a date with known data and assert exact row count and values.
- [ ] **Backfill "completed":** Often missing -- verification that no date gaps exist in the loaded range; cross-reference with source's known publication dates. Verify: query `SELECT COUNT(DISTINCT observation_date)` and compare against expected business day count for the date range.
- [ ] **Point-in-time queries "work":** Often missing -- test with a known revision (e.g., NFP for a month that was revised 3 times) and assert that `get_as_of()` returns different values for different as-of dates. Verify: `get_as_of('NFP', '2024-02-02')` returns the first release, `get_as_of('NFP', '2024-03-30')` returns the revision.
- [ ] **Yield curve "constructed":** Often missing -- validation against independent source (ANBIMA indicative rates); forward rate continuity check; no negative forwards for normal market conditions. Verify: plot forward rates and visually inspect for discontinuities; compare 1Y, 5Y, 10Y points against ANBIMA.
- [ ] **Compression "enabled":** Often missing -- verification that `segmentby` and `orderby` are set correctly; that the compression delay exceeds the maximum revision lag; that disk headroom is sufficient for temporary decompression. Verify: `SELECT * FROM timescaledb_information.compression_settings`.
- [ ] **Holiday calendar "integrated":** Often missing -- edge case testing for Carnival (date changes every year), Corpus Christi, and city-level holidays (Sao Paulo has extra holidays not observed by Rio). Verify: generate business days for 2024 and diff against ANBIMA's published calendar.
- [ ] **Timezone handling "correct":** Often missing -- test with a date during DST transition (e.g., March 2018 when Brazil still observed DST); verify pre-2019 historical data converts correctly. Verify: assert that a BCB release on the day clocks change has the correct UTC timestamp.
- [ ] **CFTC data "complete":** Often missing -- handling of weeks where a contract drops below 20 reportable traders and disappears from the report; handling of trader reclassifications that create discontinuities. Verify: check for gaps in weekly series and document expected vs actual observation counts.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Look-ahead bias in stored data | HIGH | Must reingest all affected series with full vintage history from ALFRED/BCB; rebuild all derived data; re-validate all signals built on the contaminated data. Budget 2-4 weeks. |
| Silent data gaps from API failures | MEDIUM | Identify gap boundaries from `data_quality_log`; targeted backfill for missing date ranges; verify with source publication calendar. Budget 1-3 days per source. |
| Brazilian date/number format misparse | HIGH | Identify all affected rows (hard: correctly-parsed and incorrectly-parsed values look plausible); reingest from source with correct parser; cascade corrections through derived data. Budget 1-2 weeks. |
| Compression policy blocking backfill | LOW | Disable compression policy; decompress affected chunks; run backfill; re-enable compression. Budget hours, not days, if you have disk headroom. |
| Curve construction errors | MEDIUM | Rewrite bootstrap/interpolation logic; regenerate all historical curve data; re-validate signals. Budget 1-2 weeks. |
| Timezone misalignment | HIGH | Audit all stored timestamps to determine which are correct and which are offset; reingest with correct timezone handling; rebuild all cross-market joins. Budget 2-3 weeks. |
| Duplicate rows from non-idempotent backfill | MEDIUM | Identify duplicates by natural key; DELETE duplicates keeping the most recent ingestion; add unique constraint; rewrite pipeline to use UPSERT. Budget 2-5 days. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Look-ahead bias (no PIT) | Phase 1: Schema Design | Query `get_as_of()` with known revision dates; assert different values returned |
| Free API fragility | Phase 2: Ingestion Layer | Monitor dashboard shows per-source success rates; no series stale beyond threshold |
| Brazilian format misparse | Phase 2: Ingestion Layer | Round-trip test: ingest known BR-format file, assert correct float and date values |
| Compression destroying backfill | Phase 1 (config) + Phase 3 (ordering) | Backfill completes before compression enabled; UPSERT on compressed chunk succeeds |
| Curve construction from proxy | Phase 4: Derived Data | Compare constructed curve against ANBIMA indicative rates; forward rate continuity |
| Timezone misalignment | Phase 1 (schema) + Phase 2 (ingestion) | Cross-market join produces correct alignment during DST transition week |
| Non-idempotent backfill | Phase 2 (UPSERT pattern) + Phase 3 (execution) | Run same backfill twice; assert identical row counts and values |
| Contract name instability (CFTC) | Phase 2: Ingestion Layer | Use `cftc_contract_market_code`, not text name; verify historical continuity |
| ANBIMA holiday edge cases | Phase 1: Calendar setup | Diff generated calendar against ANBIMA published calendar for 3 years |
| Schema evolution breaking consumers | Phase 5: API Layer | Add column to staging; verify downstream queries and AI agent still work |
| Survivorship bias in equity data | Phase 2: Ingestion Layer | Include delisted stocks in universe; verify backtest uses point-in-time constituents |

## Sources

### Authoritative / Official
- [FRED API Documentation](https://fred.stlouisfed.org/docs/api/fred/) -- Vintage dates, real-time periods
- [Philadelphia Fed Real-Time Data Set](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/real-time-data-set-for-macroeconomists) -- Macro data vintages
- [CFTC Historical Compressed Data](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm) -- COT data formats
- [CFTC Historical Special Announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm) -- Format changes, reclassifications
- [TimescaleDB Compression Documentation](https://docs.timescale.com/use-timescale/latest/compression/) -- Compression policies, DML on compressed data
- [TimescaleDB Hypertable Troubleshooting](https://docs.tigerdata.com/use-timescale/latest/hypertables/troubleshooting/) -- Chunk sizing, index strategies
- [US Treasury Yield Curve Methodology Change](https://home.treasury.gov/policy-issues/financing-the-government/yield-curve-methodology-change-information-sheet) -- Monotone convex adoption
- [ANBIMA Calendar Documentation](https://anbima-calendar.readthedocs.io/en/latest/introduction.html) -- Brazilian business days

### Community / Library Documentation
- [fredapi (GitHub)](https://github.com/mortada/fredapi) -- Python FRED/ALFRED interface; vintage date handling
- [python-bcb (GitHub)](https://github.com/wilsonfreitas/python-bcb) -- BCB SGS/PTAX/OData wrapper
- [pySGS Documentation](https://pysgs.readthedocs.io/) -- BCB SGS API interface
- [PYield (PyPI)](https://pypi.org/project/PYield/) -- Brazilian fixed income; date format handling
- [cot_reports (GitHub)](https://github.com/NDelventhal/cot_reports) -- CFTC COT data parsing
- [yfinance Issues #2125, #2128, #2422](https://github.com/ranaroussi/yfinance/issues/2422) -- Rate limiting documentation

### Research / Academic
- [Hagan & West (2006) "Interpolation Methods for Curve Construction"](https://www.deriscope.com/docs/Hagan_West_curves_AMF.pdf) -- Bootstrap/interpolation coupling
- [Macrosynergy: Quantitative Methods for Macro Information Efficiency](https://macrosynergy.com/research/quantitative-methods/) -- PIT data, revision bias, model parsimony
- [CEIC Point-in-Time Data Launch](https://info.ceicdata.com/ceic-launches-point-in-time-data) -- NFP PIT case study
- [Refinitiv: Using Point-in-Time Data to Avoid Bias](https://www.refinitiv.com/perspectives/future-of-investing-trading/how-to-use-point-in-time-data-to-avoid-bias-in-backtesting/) -- PIT methodology
- [Portfolio Optimization Book: Seven Sins of Quantitative Investing](https://bookdown.org/palomar/portfoliooptimizationbook/8.2-seven-sins.html) -- Survivorship bias, data snooping

### Data Engineering Best Practices
- [Building Idempotent Data Pipelines (ml4devs)](https://www.ml4devs.com/what-is/backfilling-data/) -- Backfill patterns
- [Idempotent Data Pipelines at Scale (Towards Data Engineering)](https://medium.com/towards-data-engineering/building-idempotent-data-pipelines-a-practical-guide-to-reliability-at-scale-2afc1dcb7251) -- UPSERT, dedup, audit
- [Database Backfill: Methods, Best Practices & Pitfalls (Galaxy)](https://www.getgalaxy.io/learn/glossary/database-backfill) -- Chunking, staging
- [Timezone Consistency in Data Pipelines (DZone)](https://dzone.com/articles/cross-time-zone-integrity-pipelines) -- UTC storage, DST handling
- [UTC for Trading Infrastructure (TimeStored)](https://www.timestored.com/data/utc-finance-infra) -- Financial timezone best practices
- [Lessons from Building AI Agents for Financial Services](https://www.nicolasbustamante.com/p/lessons-from-building-ai-agents-for) -- AI agent data consumption patterns

---
*Pitfalls research for: Macro Trading Data Infrastructure*
*Researched: 2026-02-19*
