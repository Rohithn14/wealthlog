# Graph Report - .  (2026-06-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1456 nodes · 3713 edges · 89 communities (73 shown, 16 thin omitted)
- Extraction: 67% EXTRACTED · 33% INFERRED · 0% AMBIGUOUS · INFERRED: 1242 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7e52f172`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Web UI Panels|Web UI Panels]]
- [[_COMMUNITY_Dashboard & Data Fetchers|Dashboard & Data Fetchers]]
- [[_COMMUNITY_FastAPI App Bootstrap|FastAPI App Bootstrap]]
- [[_COMMUNITY_DB Session & Seeding|DB Session & Seeding]]
- [[_COMMUNITY_CLI Integration Tests|CLI Integration Tests]]
- [[_COMMUNITY_Portfolio Service Tests|Portfolio Service Tests]]
- [[_COMMUNITY_Investment CLI Commands|Investment CLI Commands]]
- [[_COMMUNITY_Budget & Dividend Reports|Budget & Dividend Reports]]
- [[_COMMUNITY_SQLModel Table Definitions|SQLModel Table Definitions]]
- [[_COMMUNITY_Price Cache Service|Price Cache Service]]
- [[_COMMUNITY_DB Types & CSV Importer|DB Types & CSV Importer]]
- [[_COMMUNITY_Service Result Objects|Service Result Objects]]
- [[_COMMUNITY_Income & Expense Services|Income & Expense Services]]
- [[_COMMUNITY_FD Enums & Constants Tests|FD Enums & Constants Tests]]
- [[_COMMUNITY_CLI Output Formatting|CLI Output Formatting]]
- [[_COMMUNITY_Alert Service Tests|Alert Service Tests]]
- [[_COMMUNITY_Liability & Net Worth Services|Liability & Net Worth Services]]
- [[_COMMUNITY_FX Caching Tests|FX Caching Tests]]
- [[_COMMUNITY_Config & Cache TTL Tests|Config & Cache TTL Tests]]
- [[_COMMUNITY_Market Data Fetchers|Market Data Fetchers]]
- [[_COMMUNITY_Expense CLI Commands|Expense CLI Commands]]
- [[_COMMUNITY_Alert Rules Service|Alert Rules Service]]
- [[_COMMUNITY_Web UI End-to-End Tests|Web UI End-to-End Tests]]
- [[_COMMUNITY_API Models & Tests|API Models & Tests]]
- [[_COMMUNITY_Decimal Type Tests|Decimal Type Tests]]
- [[_COMMUNITY_Fetcher Protocols|Fetcher Protocols]]
- [[_COMMUNITY_Income Service Tests|Income Service Tests]]
- [[_COMMUNITY_FD Valuation Tests|FD Valuation Tests]]
- [[_COMMUNITY_Budget Service Tests|Budget Service Tests]]
- [[_COMMUNITY_Net Worth Service Tests|Net Worth Service Tests]]
- [[_COMMUNITY_PDF Report Generation|PDF Report Generation]]
- [[_COMMUNITY_Dividend Service Tests|Dividend Service Tests]]
- [[_COMMUNITY_Import Service Tests|Import Service Tests]]
- [[_COMMUNITY_XIRR Tests|XIRR Tests]]
- [[_COMMUNITY_CSV & Export Services|CSV & Export Services]]
- [[_COMMUNITY_Benchmark Service Tests|Benchmark Service Tests]]
- [[_COMMUNITY_Import & Liability CLI|Import & Liability CLI]]
- [[_COMMUNITY_DecimalText Column Tests|DecimalText Column Tests]]
- [[_COMMUNITY_Concentration Service Tests|Concentration Service Tests]]
- [[_COMMUNITY_Budget Status & Dashboard|Budget Status & Dashboard]]
- [[_COMMUNITY_Alert & Category CLI|Alert & Category CLI]]
- [[_COMMUNITY_YFinance Fetcher Tests|YFinance Fetcher Tests]]
- [[_COMMUNITY_Expense Service Tests|Expense Service Tests]]
- [[_COMMUNITY_Export Service Tests|Export Service Tests]]
- [[_COMMUNITY_SIP Service Tests|SIP Service Tests]]
- [[_COMMUNITY_FIFO Capital Gains Tax|FIFO Capital Gains Tax]]
- [[_COMMUNITY_SIP Schedule Service|SIP Schedule Service]]
- [[_COMMUNITY_Fetcher Service & Snapshots|Fetcher Service & Snapshots]]
- [[_COMMUNITY_Portfolio Service Core|Portfolio Service Core]]
- [[_COMMUNITY_Recurring Expense Tests|Recurring Expense Tests]]
- [[_COMMUNITY_Tax Service Tests|Tax Service Tests]]
- [[_COMMUNITY_Dashboard Assembly Tests|Dashboard Assembly Tests]]
- [[_COMMUNITY_CLI Render Helpers|CLI Render Helpers]]
- [[_COMMUNITY_Income CLI Commands|Income CLI Commands]]
- [[_COMMUNITY_Benchmark Service|Benchmark Service]]
- [[_COMMUNITY_Expense Service CRUD|Expense Service CRUD]]
- [[_COMMUNITY_Broker Import Service|Broker Import Service]]
- [[_COMMUNITY_CLI Smoke Tests|CLI Smoke Tests]]
- [[_COMMUNITY_TUI Tests|TUI Tests]]
- [[_COMMUNITY_Export CLI Commands|Export CLI Commands]]
- [[_COMMUNITY_Add Expense Tests|Add Expense Tests]]
- [[_COMMUNITY_Alert Watcher Script|Alert Watcher Script]]
- [[_COMMUNITY_Budget CLI Commands|Budget CLI Commands]]
- [[_COMMUNITY_Financial Year Utilities|Financial Year Utilities]]
- [[_COMMUNITY_NAV & Price Fetcher Tests|NAV & Price Fetcher Tests]]
- [[_COMMUNITY_CLI Entry Point|CLI Entry Point]]
- [[_COMMUNITY_Alembic Migrations|Alembic Migrations]]
- [[_COMMUNITY_Monthly Summary Tests|Monthly Summary Tests]]
- [[_COMMUNITY_Historical Net Worth Tests|Historical Net Worth Tests]]
- [[_COMMUNITY_Logging Utilities|Logging Utilities]]
- [[_COMMUNITY_FX Rate Cache|FX Rate Cache]]
- [[_COMMUNITY_Liability Reporting|Liability Reporting]]
- [[_COMMUNITY_XIRR Calculator|XIRR Calculator]]
- [[_COMMUNITY_Alert Watcher Package|Alert Watcher Package]]
- [[_COMMUNITY_Web UI Package|Web UI Package]]
- [[_COMMUNITY_CLI Package|CLI Package]]
- [[_COMMUNITY_Database Package|Database Package]]
- [[_COMMUNITY_Export Package|Export Package]]
- [[_COMMUNITY_Fetchers Package|Fetchers Package]]
- [[_COMMUNITY_Financial Calculations Package|Financial Calculations Package]]
- [[_COMMUNITY_Services Package|Services Package]]
- [[_COMMUNITY_FastAPI Sidecar Package|FastAPI Sidecar Package]]
- [[_COMMUNITY_TUI Package|TUI Package]]
- [[_COMMUNITY_Wealthlog Root Package|Wealthlog Root Package]]
- [[_COMMUNITY_Wealthlog Namespace|Wealthlog Namespace]]
- [[_COMMUNITY_Price Snapshots & Recurrence|Price Snapshots & Recurrence]]
- [[_COMMUNITY_Import Preview Model|Import Preview Model]]

## God Nodes (most connected - your core abstractions)
1. `PortfolioService` - 132 edges
2. `AssetType` - 126 edges
3. `TransactionType` - 101 edges
4. `PriceCache` - 80 edges
5. `session_scope()` - 76 edges
6. `ExpenseService` - 66 edges
7. `FetcherService` - 66 edges
8. `Investment` - 53 edges
9. `CompoundingFrequency` - 48 edges
10. `Category` - 46 edges

## Surprising Connections (you probably didn't know these)
- `svc()` --calls--> `AlertService`  [INFERRED]
  tests/test_alerts_service.py → src/wealthlog/services/alerts.py
- `svc()` --calls--> `BenchmarkService`  [INFERRED]
  tests/test_benchmark_service.py → src/wealthlog/services/benchmark.py
- `budget_svc()` --calls--> `BudgetService`  [INFERRED]
  tests/test_budget_service.py → src/wealthlog/services/budget.py
- `expense_svc()` --calls--> `ExpenseService`  [INFERRED]
  tests/test_budget_service.py → src/wealthlog/services/expense.py
- `svc()` --calls--> `ExpenseService`  [INFERRED]
  tests/test_expense_service.py → src/wealthlog/services/expense.py

## Import Cycles
- None detected.

## Communities (89 total, 16 thin omitted)

### Community 0 - "Web UI Panels"
Cohesion: 0.06
Nodes (70): _add_fd_form(), _add_investment_panel(), _add_stock_form(), _alert_add_view(), _alert_check_view(), _alert_rules_view(), _allocation_chart_options(), _analysis_panel() (+62 more)

### Community 1 - "Dashboard & Data Fetchers"
Cohesion: 0.06
Nodes (35): Headless data aggregation for the web/TUI dashboards.  Pure read functions that, datetime, Seed data: default expense categories.  Idempotent — running it repeatedly will, USD→INR (and general) FX fetcher backed by the free frankfurter.app API., Indian mutual-fund NAV fetcher backed by the free mfapi.in REST API., Equity / ETF price fetcher backed by yfinance (Yahoo Finance).  Covers NSE/BSE s, Fixed-deposit / debt-instrument valuation.  FDs have no live market price; their, XIRR (money-weighted annualised return) calculation.  Wraps :mod:`pyxirr` (fast, (+27 more)

### Community 2 - "FastAPI App Bootstrap"
Cohesion: 0.05
Nodes (27): App, CLI database bootstrap helpers (re-exported from :mod:`wealthlog.bootstrap`)., FastAPI, create_app(), main(), _money(), FastAPI application for the wealthlog sidecar (C1 IPC contract).  Endpoints (mon, Build the sidecar FastAPI app (factory keeps it import-test friendly). (+19 more)

### Community 3 - "DB Session & Seeding"
Cohesion: 0.07
Nodes (24): Insert default categories if they do not already exist.      Args:         sessi, seed_categories(), _build_engine(), create_db_and_tables(), get_engine(), get_session(), Database engine and session management.  Provides a process-wide engine bound to, Return the process-wide SQLAlchemy engine, creating it on first use.      The en (+16 more)

### Community 4 - "CLI Integration Tests"
Cohesion: 0.08
Nodes (10): Integration tests for the Typer CLI (in-memory DB via the autouse fixture)., run(), TestBudgetCommands, TestCategoryCommands, TestExpenseCommands, TestInvestCommands, TestLiabilityCommands, TestMachineOutput (+2 more)

### Community 5 - "Portfolio Service Tests"
Cohesion: 0.05
Nodes (11): _add_price(), Tests for PortfolioService: transactions, holdings, P&L, XIRR, FD valuation., Regression tests for `_validate_transaction` (bugs #9-gap, #10, #11)., Bug #5: a matured FD's terminal flow must be dated at maturity, not as_of., svc(), TestAddTransaction, TestHoldings, TestMaturedFdXirr (+3 more)

### Community 6 - "Investment CLI Commands"
Cohesion: 0.10
Nodes (38): add_fd(), add_investment(), add_sip_schedule(), benchmark(), benchmark_price(), buy(), concentration(), dividends() (+30 more)

### Community 7 - "Budget & Dividend Reports"
Cohesion: 0.08
Nodes (15): Create or update the budget for a category and month (upsert).          Args:, Build a concentration report from current holdings.          Args:             t, Total dividends received per calendar year (INR), newest first., Per-investment dividend totals, optionally filtered to one year.          Return, Trailing-12-month dividends as a percentage of current market value.          Re, Add a new expense.          Args:             date: The expense date., Total income per category name for a calendar month.          Raises:, Income minus expenses for a calendar month. (+7 more)

### Community 8 - "SQLModel Table Definitions"
Cohesion: 0.09
Nodes (26): Account, Budget, Expense, FdDetails, Investment, SQLModel table definitions for wealthlog.  All monetary values are stored in INR, A per-category monthly spending limit (INR)., An investment holding (stock, MF, gold ETF, or FD). (+18 more)

### Community 9 - "Price Cache Service"
Cohesion: 0.20
Nodes (6): PriceCache, A cached latest price for an investment, in native currency and INR., Return the latest NAV for a scheme code (INR), using cached price rows., Keep only the latest ``_CACHE_KEEP`` price rows per investment.          ``price, Refresh cached prices for every non-FD investment.          For USD assets the n, Manually record an INR price for an investment (override / fallback).          A

### Community 10 - "DB Types & CSV Importer"
Cohesion: 0.12
Nodes (22): Custom SQLAlchemy column types.  SQLite has no native DECIMAL type — its NUMERIC, Decimal, Numeric, _dec(), _parse_date(), parse_generic(), parse_zerodha(), ParsedTxn (+14 more)

### Community 11 - "Service Result Objects"
Cohesion: 0.12
Nodes (28): BenchmarkComparison, BenchmarkReturn, CashflowSummary, ConcentrationReport, ConcentrationRow, DividendRow, MonthlySummary, NetWorthPoint (+20 more)

### Community 12 - "Income & Expense Services"
Cohesion: 0.08
Nodes (19): date, Income, A single dated income entry in INR (salary, dividend payout, interest…)., Summarise expenses for a calendar month.          Args:             year: Four-d, List expenses matching optional filters, newest first.          Args:, Add a new income entry.          Args:             date: The income date., List income entries matching optional filters, newest first., _latest_snapshot_price() (+11 more)

### Community 13 - "FD Enums & Constants Tests"
Cohesion: 0.09
Nodes (15): A rule that materialises an :class:`Expense` on a fixed cadence., RecurringExpense, fd_accrued_interest(), Return only the accrued interest portion of an FD (value − principal)., Tests for enums and constant invariants., TestCompounding, TestEnums, TestInflowTypes (+7 more)

### Community 14 - "CLI Output Formatting"
Cohesion: 0.13
Nodes (26): emit(), fmt_inr(), make_table(), OutputFormat, Create a rich table with a title and right-aligned numeric look., Output format for read commands (``--format``)., Print ``obj`` as JSON or CSV (pipe-friendly, no rich markup).      JSON preserve, Format a Decimal as an INR string with thousands separators. (+18 more)

### Community 15 - "Alert Service Tests"
Cohesion: 0.14
Nodes (9): _add_price(), _category(), portfolio(), Tests for AlertService: rule CRUD, evaluation per kind, and same-day dedup., svc(), TestBudgetPct, TestDedup, TestPriceDrop (+1 more)

### Community 16 - "Liability & Net Worth Services"
Cohesion: 0.11
Nodes (15): Liability, A debt (loan, credit-card balance, …) that offsets net worth., LiabilityService, Manage liabilities and report their total.      Args:         session: An open d, Create and persist a liability., Delete a liability; ``True`` if it existed., NetWorthService, Compute net worth and historical invested-capital series.      Args:         ses (+7 more)

### Community 17 - "FX Caching Tests"
Cohesion: 0.18
Nodes (7): FxQuote, A foreign-exchange rate quote for a currency pair., FakeFxFetcher, Tests for FetcherService: caching, INR conversion, fallback, manual override., Bug #8 / 2a: append-only caches are bounded to the latest 5 rows., TestCachePruning, TestFxCaching

### Community 18 - "Config & Cache TTL Tests"
Cohesion: 0.12
Nodes (13): Tests for application configuration and cache-TTL resolution., TestAppConfig, TestCacheTTL, TestDatabaseUrl, TestDataDir, timedelta, CacheTTLConfig, get_data_dir() (+5 more)

### Community 19 - "Market Data Fetchers"
Cohesion: 0.14
Nodes (12): Client, Exception, FetchError, Raised when a market-data source fails or returns unusable data., FrankfurterFetcher, Fetch a latest FX rate from ``api.frankfurter.app/latest``.      Args:         c, Return the latest exchange rate for ``base`` → ``quote``.          Args:, MfApiFetcher (+4 more)

### Community 20 - "Expense CLI Commands"
Cohesion: 0.11
Nodes (19): add_expense(), add_recurring(), deactivate_recurring(), delete_expense(), generate_recurring(), list_recurring(), _parse_date(), `wealthlog-cli expense` commands. (+11 more)

### Community 21 - "Alert Rules Service"
Cohesion: 0.14
Nodes (15): AlertEvent, AlertRule, A user-defined condition evaluated by the alerts watcher (C3)., A fired alert, kept for same-day de-duplication and history., AlertService, Human-readable target for a rule (symbol/category/all)., Manage alert rules and evaluate them against current portfolio state.      Args:, Create an alert rule.          Raises:             ValueError: If a threshold is (+7 more)

### Community 22 - "Web UI End-to-End Tests"
Cohesion: 0.13
Nodes (21): MonkeyPatch, _patch_refresh(), End-to-end tests for the NiceGUI web UI (``wealthlog.api.server``).  These drive, A category create through the form persists and notifies success., Every action button is clickable with empty/default forms.      Invalid input mu, Seeded data renders through the dashboard and holdings read paths., Net-worth read flow renders with seeded data., WUI-1 regression: the async refresh handler runs in the client slot.      Before (+13 more)

### Community 23 - "API Models & Tests"
Cohesion: 0.24
Nodes (10): BaseModel, Category, An expense or income category., ExpenseIn, TransactionIn, TestAllocationSeries, TestFd, TestFormatting (+2 more)

### Community 24 - "Decimal Type Tests"
Cohesion: 0.10
Nodes (9): Serialize a Decimal to a canonical string for storage., Deserialize stored TEXT back into an exact Decimal., Tests for the Decimal money/price/FX/unit helpers.  Broad coverage: precision pe, TestToDecimal, TestToFx, TestToPrice, TestToUnits, Coerce a value to :class:`Decimal` safely.      Args:         value: A Decimal, (+1 more)

### Community 25 - "Fetcher Protocols"
Cohesion: 0.12
Nodes (12): FxFetcher, NavFetcher, PriceFetcher, Fetcher protocols and shared types.  Fetchers are thin wrappers over external da, Fetches a latest price for an exchange-listed symbol., Fetches the latest NAV for an Indian mutual-fund scheme code., Fetches a latest FX rate for a currency pair., Protocol (+4 more)

### Community 26 - "Income Service Tests"
Cohesion: 0.11
Nodes (8): _delete_income(), IncomeService, CRUD and reporting for income entries.      Args:         session: An open datab, Delete an income entry by id; ``True`` if a row was deleted., Tests for IncomeService: CRUD, monthly summary, and net cashflow., svc(), TestAddIncome, TestListAndSummary

### Community 27 - "FD Valuation Tests"
Cohesion: 0.15
Nodes (8): calculate_fd_value(), _decimal_pow(), Raise ``base`` to a (possibly fractional) ``exponent`` using Decimal exp/ln., Value a fixed deposit as of a given date.      Args:         principal: The depo, Tests for fixed-deposit valuation (simple & compound, clamping, edge cases)., TestClamping, TestCompounding, TestSimpleInterest

### Community 28 - "Budget Service Tests"
Cohesion: 0.10
Nodes (6): budget_svc(), expense_svc(), Tests for BudgetService: upsert, status computation, overage alerts., TestAlerts, TestBudgetStatus, TestSetBudget

### Community 29 - "Net Worth Service Tests"
Cohesion: 0.12
Nodes (10): _add_price(), _add_snapshot(), portfolio(), Tests for NetWorthService: asset-class breakdown and historical series., Bug #4b: a SELL releases the average cost of sold units, not the proceeds., A3: market mode values holdings from snapshots, falling back to cost., svc(), TestHistoricalSellCostBasis (+2 more)

### Community 30 - "PDF Report Generation"
Cohesion: 0.16
Nodes (14): ComposeResult, build_pdf_report(), PDF report generation using fpdf2 (pure-Python, no system libraries).  A bundled, Render a formatted PDF report with net-worth and portfolio summaries.      Args:, _ReportPdf, _rs(), _table(), FPDF (+6 more)

### Community 31 - "Dividend Service Tests"
Cohesion: 0.18
Nodes (9): DividendService, Aggregate dividends by year/holding and compute trailing yield.      Args:, _add_price(), _dividend(), portfolio(), Tests for DividendService: yearly/holding aggregation and trailing yield., svc(), TestAggregation (+1 more)

### Community 32 - "Import Service Tests"
Cohesion: 0.17
Nodes (7): portfolio(), Tests for ImportService: parsing, dedup preview, and commit., svc(), TestCommit, TestParse, TestPreview, _write()

### Community 33 - "XIRR Tests"
Cohesion: 0.11
Nodes (4): Tests for XIRR calculation across many scenarios., TestBasic, TestEdgeCases, TestMultiFlow

### Community 34 - "CSV & Export Services"
Cohesion: 0.20
Nodes (11): CSV export helpers (stdlib ``csv``)., Write a CSV file with a header row and data rows.      Args:         path: Desti, write_csv(), Path, ExportService, Export a formatted PDF report (net worth + portfolio summary).          Args:, Produce CSV extracts and PDF reports from stored data.      Args:         sessio, Export a dataset to CSV.          Args:             kind: One of ``"expenses"``, (+3 more)

### Community 35 - "Benchmark Service Tests"
Cohesion: 0.12
Nodes (6): portfolio(), Tests for BenchmarkService: snapshot-based returns and portfolio comparison., svc(), TestBenchmarkReturn, TestBenchmarkSetup, TestCompare

### Community 36 - "Import & Liability CLI"
Cohesion: 0.17
Nodes (14): Argument, generic(), `wealthlog-cli import` commands — broker statement import (B3)., Import a Zerodha tradebook (dry run by default)., Import a CSV in the documented generic schema (dry run by default).      Columns, _run(), zerodha(), deactivate_sip_schedule() (+6 more)

### Community 37 - "DecimalText Column Tests"
Cohesion: 0.20
Nodes (7): DecimalText, Store a :class:`Decimal` as exact TEXT, preserving full precision.      Args:, Tests for the DecimalText column type — the precision-preserving core of storage, TestBindParam, TestResultValue, TestRoundTrip, TypeDecorator

### Community 38 - "Concentration Service Tests"
Cohesion: 0.18
Nodes (8): ConcentrationService, Compute single-name, sector, and asset-class concentration.      Args:         s, _add_price(), _holding(), portfolio(), Tests for ConcentrationService: single-name, sector, and asset-class weights., svc(), TestConcentration

### Community 39 - "Budget Status & Dashboard"
Cohesion: 0.18
Nodes (9): DashboardData, Everything the dashboard needs for a single render., BudgetService, Return only the budget statuses that are over their limit., Set monthly spending limits and report status against actual spending.      Args, Return budget-vs-spent status for every budgeted category in a month.          A, BudgetStatus, Spending status for one category against its monthly budget. (+1 more)

### Community 40 - "Alert & Category CLI"
Cohesion: 0.17
Nodes (13): add_rule(), check(), deactivate(), list_rules(), `wealthlog-cli alert` commands — manage and test portfolio alerts (C3)., Create an alert rule., Deactivate an alert rule., Evaluate alert rules now and print any that fire. (+5 more)

### Community 41 - "YFinance Fetcher Tests"
Cohesion: 0.22
Nodes (5): Fetch the latest price for an exchange-listed symbol via yfinance., Return ``(last_price, currency)`` from yfinance (isolated for testing)., Return the latest price quote for a symbol.          Args:             symbol: y, YFinanceFetcher, TestYFinanceFetcher

### Community 42 - "Expense Service Tests"
Cohesion: 0.18
Nodes (4): Tests for ExpenseService: add, list/filter, monthly summary, delete., svc(), TestDelete, TestListExpenses

### Community 43 - "Export Service Tests"
Cohesion: 0.17
Nodes (8): export_svc(), Tests for ExportService and the CSV/PDF exporters., _read_csv(), TestCsvDirectoryCreation, TestCsvErrors, TestCsvExpenses, TestCsvHoldings, TestCsvTransactions

### Community 44 - "SIP Service Tests"
Cohesion: 0.13
Nodes (5): portfolio(), Tests for SIPService: schedules and pending-instalment detection., svc(), TestAddSchedule, TestPendingSips

### Community 45 - "FIFO Capital Gains Tax"
Cohesion: 0.24
Nodes (11): deque, CapitalGainsReport, GainRow, One FIFO-matched realised gain: a SELL slice against a single buy lot., Capital-gains summary for one financial year (informational, not advice)., _Lot, Build a FIFO capital-gains report for an Indian financial year.          Args:, An open buy lot: remaining units carry a per-unit INR cost. (+3 more)

### Community 46 - "SIP Schedule Service"
Cohesion: 0.19
Nodes (8): An expected monthly SIP instalment against an investment., SIPSchedule, Manage SIP schedules and report instalments that are due but unrecorded.      Ar, List SIP schedules (active only by default)., Deactivate a schedule; ``True`` if it existed., Return instalments due on/before ``as_of`` with no SIP transaction.          A d, SIPService, TestSipDue

### Community 47 - "Fetcher Service & Snapshots"
Cohesion: 0.24
Nodes (6): FetcherService, Fetch and cache prices, NAVs, and FX rates.      Args:         session: An open, FakePriceFetcher, A3: every stored price also upserts one PriceSnapshot per investment per day., TestPriceSnapshots, TestRefreshPrices

### Community 48 - "Portfolio Service Core"
Cohesion: 0.18
Nodes (6): PortfolioService, Manage investments, transactions, and portfolio analytics.      Args:         se, Create an investment record and return it., Set/clear an investment's sector tag; ``True`` if it existed., TestPdf, portfolio()

### Community 49 - "Recurring Expense Tests"
Cohesion: 0.15
Nodes (4): Tests for RecurringExpenseService: rule CRUD and idempotent generation., svc(), TestAddRule, TestGenerate

### Community 50 - "Tax Service Tests"
Cohesion: 0.15
Nodes (5): portfolio(), Tests for TaxService: FIFO matching, LTCG/STCG classification, FY summary., svc(), TestFifoMatching, TestTaxEstimates

### Community 51 - "Dashboard Assembly Tests"
Cohesion: 0.24
Nodes (6): asset_allocation_series(), build_dashboard_data(), Assemble a :class:`DashboardData` snapshot from the services.      Args:, Return ``(labels, values)`` for an asset-allocation pie chart., _price(), TestBuildDashboardData

### Community 52 - "CLI Render Helpers"
Cohesion: 0.18
Nodes (11): fmt_pct(), fmt_ratio_as_pct(), _jsonable(), Shared CLI rendering helpers (rich tables, INR/percent formatting, machine outpu, Recursively coerce a value to JSON/CSV-friendly primitives., Normalise dataclasses / SQLModel rows (and lists of them) to plain dicts., Format a Decimal percentage (already in percent units) with a sign., Format a ratio (e.g. 0.0997) as a percentage string (9.97%). (+3 more)

### Community 53 - "Income CLI Commands"
Cohesion: 0.20
Nodes (11): add_income(), delete_income(), list_income(), _parse_date(), `wealthlog-cli income` commands., Delete an income entry by id., Add an income entry (date defaults to today)., List income entries, optionally filtered by date range. (+3 more)

### Community 54 - "Benchmark Service"
Cohesion: 0.21
Nodes (8): BenchmarkService, _pow(), Compare portfolio XIRR against each benchmark's CAGR over a window., Decimal ``base ** exp`` via float (precision is ample for CAGR display)., Manage benchmark pseudo-investments and compute index returns.      Args:, Return (creating if needed) the pseudo-investment for a benchmark name., Upsert a benchmark price snapshot (one per benchmark per day)., Return a benchmark's growth between the snapshots bounding [start, end].

### Community 55 - "Expense Service CRUD"
Cohesion: 0.22
Nodes (6): _delete_expense(), ExpenseService, Delete an expense by id.          Returns:             ``True`` if a row was del, CRUD and reporting for expenses.      Args:         session: An open database se, Return an expense by id, or ``None`` if not found., TestNetCashflow

### Community 56 - "Broker Import Service"
Cohesion: 0.29
Nodes (5): ImportService, Preview and commit broker-statement imports.      Args:         session: An open, Parse a file with the named broker parser (rows sorted by date)., Dry-run: parse and tag each row as new or duplicate (no writes)., Import non-duplicate rows, auto-creating investments as needed.

### Community 57 - "CLI Smoke Tests"
Cohesion: 0.20
Nodes (3): Smoke tests for the CLI skeleton and interface entry points., TestCliSkeleton, TestEntryPointsImportable

### Community 58 - "TUI Tests"
Cohesion: 0.33
Nodes (3): Tests for the Textual TUI, driven through the async test pilot.  We wrap each sc, _run(), TestAppMounts

### Community 59 - "Export CLI Commands"
Cohesion: 0.25
Nodes (7): export_csv(), export_pdf(), `wealthlog-cli export` commands., Export expenses, transactions, or holdings to CSV., Export a formatted PDF report (net worth + portfolio summary)., CSV_KINDS, join

### Community 61 - "Alert Watcher Script"
Cohesion: 0.38
Nodes (6): _deliver(), main(), ``wealthlog-alerts`` console script — evaluate alert rules and deliver them.  De, Best-effort desktop notification plus stdout., Evaluate alerts once; return the number fired., run_once()

### Community 62 - "Budget CLI Commands"
Cohesion: 0.33
Nodes (6): alerts(), `wealthlog-cli budget` commands., Set (or update) a category's monthly budget., List categories that are over budget for a month., _resolve_category(), set_budget()

### Community 63 - "Financial Year Utilities"
Cohesion: 0.43
Nodes (3): financial_year_bounds(), Return (start, end) dates for an Indian FY string like ``"2025-26"``.      Raise, TestFinancialYearBounds

### Community 64 - "NAV & Price Fetcher Tests"
Cohesion: 0.21
Nodes (6): NavQuote, PriceQuote, A native-currency price quote for a symbol., An Indian mutual-fund NAV quote (published end-of-day)., FakeNavFetcher, TestNavAndManual

### Community 65 - "CLI Entry Point"
Cohesion: 0.33
Nodes (5): _main(), wealthlog command-line interface (Typer).  Scriptable entry point exposed as the, wealthlog — local-first personal finance & investment tracker., Print the installed wealthlog version., version()

### Community 66 - "Alembic Migrations"
Cohesion: 0.33
Nodes (5): Alembic migration environment for wealthlog.  Wires Alembic to the SQLModel meta, Run migrations without a live DB connection (emits SQL)., Run migrations against a live DB connection., run_migrations_offline(), run_migrations_online()

### Community 69 - "Logging Utilities"
Cohesion: 0.40
Nodes (5): Logger, configure_logging(), get_logger(), Configure root logging once for the process.      Args:         level: Logging l, Return a module-scoped logger, ensuring logging is configured.      Args:

### Community 70 - "FX Rate Cache"
Cohesion: 0.33
Nodes (4): FxRate, A cached FX rate for a currency pair (e.g. USD_INR)., Return ``(rate, fetched_at)`` for a currency pair, using the cache.          Fre, Keep only the latest ``_CACHE_KEEP`` cached rates per currency pair.

### Community 71 - "Liability Reporting"
Cohesion: 0.50
Nodes (3): Return all liabilities, largest first., LiabilityRow, A single liability for display.

### Community 72 - "XIRR Calculator"
Cohesion: 0.67
Nodes (3): CashFlow, calculate_xirr(), Compute the XIRR of a series of dated cash flows.      Args:         cash_flows:

### Community 87 - "Price Snapshots & Recurrence"
Cohesion: 0.33
Nodes (5): PriceSnapshot, One closing INR price per investment per day, for historical valuation., Record today's closing price (one snapshot per investment per day)., Cadence for recurring expenses and SIP schedules., RecurrenceFrequency

## Knowledge Gaps
- **1 isolated node(s):** `wealthlog`
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PortfolioService` connect `Portfolio Service Core` to `Web UI Panels`, `Dashboard & Data Fetchers`, `FastAPI App Bootstrap`, `DB Session & Seeding`, `Portfolio Service Tests`, `Investment CLI Commands`, `Budget & Dividend Reports`, `SQLModel Table Definitions`, `Price Cache Service`, `DB Types & CSV Importer`, `Service Result Objects`, `Income & Expense Services`, `FD Enums & Constants Tests`, `CLI Output Formatting`, `Alert Service Tests`, `Liability & Net Worth Services`, `FX Caching Tests`, `Alert Rules Service`, `Web UI End-to-End Tests`, `API Models & Tests`, `Net Worth Service Tests`, `PDF Report Generation`, `Dividend Service Tests`, `Import Service Tests`, `CSV & Export Services`, `Benchmark Service Tests`, `Concentration Service Tests`, `Budget Status & Dashboard`, `Export Service Tests`, `SIP Service Tests`, `SIP Schedule Service`, `Fetcher Service & Snapshots`, `Tax Service Tests`, `Dashboard Assembly Tests`, `CLI Render Helpers`, `Benchmark Service`, `Broker Import Service`, `TUI Tests`, `Financial Year Utilities`, `NAV & Price Fetcher Tests`, `Historical Net Worth Tests`, `Import Preview Model`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `AssetType` connect `Service Result Objects` to `Dashboard & Data Fetchers`, `FastAPI App Bootstrap`, `Portfolio Service Tests`, `Investment CLI Commands`, `SQLModel Table Definitions`, `Price Cache Service`, `DB Types & CSV Importer`, `Income & Expense Services`, `FD Enums & Constants Tests`, `Alert Service Tests`, `Liability & Net Worth Services`, `FX Caching Tests`, `Config & Cache TTL Tests`, `Alert Rules Service`, `API Models & Tests`, `Fetcher Protocols`, `Net Worth Service Tests`, `PDF Report Generation`, `Dividend Service Tests`, `Import Service Tests`, `Benchmark Service Tests`, `Concentration Service Tests`, `Budget Status & Dashboard`, `Export Service Tests`, `SIP Service Tests`, `FIFO Capital Gains Tax`, `SIP Schedule Service`, `Fetcher Service & Snapshots`, `Portfolio Service Core`, `Tax Service Tests`, `Dashboard Assembly Tests`, `Benchmark Service`, `Broker Import Service`, `TUI Tests`, `Financial Year Utilities`, `NAV & Price Fetcher Tests`, `Historical Net Worth Tests`, `FX Rate Cache`, `Liability Reporting`, `Price Snapshots & Recurrence`, `Import Preview Model`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `TransactionType` connect `API Models & Tests` to `Web UI Panels`, `Dashboard & Data Fetchers`, `FastAPI App Bootstrap`, `Portfolio Service Tests`, `Investment CLI Commands`, `SQLModel Table Definitions`, `Price Cache Service`, `DB Types & CSV Importer`, `Service Result Objects`, `Income & Expense Services`, `FD Enums & Constants Tests`, `Alert Service Tests`, `Liability & Net Worth Services`, `FX Caching Tests`, `Alert Rules Service`, `Net Worth Service Tests`, `Dividend Service Tests`, `Import Service Tests`, `Benchmark Service Tests`, `Concentration Service Tests`, `Budget Status & Dashboard`, `Export Service Tests`, `SIP Service Tests`, `FIFO Capital Gains Tax`, `SIP Schedule Service`, `Fetcher Service & Snapshots`, `Portfolio Service Core`, `Tax Service Tests`, `Dashboard Assembly Tests`, `Broker Import Service`, `TUI Tests`, `Financial Year Utilities`, `NAV & Price Fetcher Tests`, `Historical Net Worth Tests`, `FX Rate Cache`, `Price Snapshots & Recurrence`, `Import Preview Model`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 115 inferred relationships involving `PortfolioService` (e.g. with `build_dashboard_data()` and `DashboardData`) actually correct?**
  _`PortfolioService` has 115 INFERRED edges - model-reasoned connections that need verification._
- **Are the 118 inferred relationships involving `AssetType` (e.g. with `Account` and `AlertEvent`) actually correct?**
  _`AssetType` has 118 INFERRED edges - model-reasoned connections that need verification._
- **Are the 93 inferred relationships involving `TransactionType` (e.g. with `Account` and `AlertEvent`) actually correct?**
  _`TransactionType` has 93 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `PriceCache` (e.g. with `DecimalText` and `AlertKind`) actually correct?**
  _`PriceCache` has 72 INFERRED edges - model-reasoned connections that need verification._