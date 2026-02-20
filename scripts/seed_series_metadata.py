"""Seed the series_metadata and data_sources tables.

Reads SERIES_REGISTRY definitions from each connector to build a comprehensive
catalogue of all data series. Idempotent via ON CONFLICT DO NOTHING.

Run: python scripts/seed_series_metadata.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.database import sync_session_factory
from src.core.models.data_sources import DataSource
from src.core.models.series_metadata import SeriesMetadata

# ---------------------------------------------------------------------------
# Data sources -- one row per external API
# ---------------------------------------------------------------------------
DATA_SOURCES = [
    {"name": "BCB_SGS", "base_url": "https://api.bcb.gov.br", "auth_type": "none", "rate_limit_per_minute": 180, "default_locale": "pt-BR", "notes": "Banco Central do Brasil - SGS time series"},
    {"name": "FRED", "base_url": "https://api.stlouisfed.org", "auth_type": "api_key", "rate_limit_per_minute": 120, "default_locale": "en-US", "notes": "Federal Reserve Economic Data"},
    {"name": "BCB_FOCUS", "base_url": "https://olinda.bcb.gov.br", "auth_type": "none", "rate_limit_per_minute": 120, "default_locale": "pt-BR", "notes": "BCB Focus survey (market expectations)"},
    {"name": "B3_MARKET_DATA", "base_url": "https://api.bcb.gov.br", "auth_type": "none", "rate_limit_per_minute": 180, "default_locale": "pt-BR", "notes": "B3/Tesouro Direto - DI curve, NTN-B rates"},
    {"name": "TREASURY_GOV", "base_url": "https://home.treasury.gov", "auth_type": "none", "rate_limit_per_minute": 120, "default_locale": "en-US", "notes": "US Treasury yield curve data"},
    {"name": "YAHOO_FINANCE", "base_url": "https://finance.yahoo.com", "auth_type": "none", "rate_limit_per_minute": 60, "default_locale": "en-US", "notes": "Yahoo Finance OHLCV market data"},
    {"name": "CFTC_COT", "base_url": "https://www.cftc.gov", "auth_type": "none", "rate_limit_per_minute": 60, "default_locale": "en-US", "notes": "CFTC Commitment of Traders positioning data"},
    {"name": "BCB_PTAX", "base_url": "https://olinda.bcb.gov.br", "auth_type": "none", "rate_limit_per_minute": 120, "default_locale": "pt-BR", "notes": "BCB PTAX official FX rate"},
    {"name": "BCB_FX_FLOW", "base_url": "https://api.bcb.gov.br", "auth_type": "none", "rate_limit_per_minute": 180, "default_locale": "pt-BR", "notes": "BCB FX flow data"},
    {"name": "IBGE_SIDRA", "base_url": "https://apisidra.ibge.gov.br", "auth_type": "none", "rate_limit_per_minute": 60, "default_locale": "pt-BR", "notes": "IBGE SIDRA - IPCA by component"},
    {"name": "STN_FISCAL", "base_url": "https://api.bcb.gov.br", "auth_type": "none", "rate_limit_per_minute": 180, "default_locale": "pt-BR", "notes": "STN Fiscal - government fiscal data from BCB SGS"},
]


def _bcb_sgs_series() -> list[dict]:
    """All 50 BCB SGS macro series."""
    return [
        # INFLATION
        {"series_code": "433", "name": "IPCA Variacao Mensal", "frequency": "M", "country": "BR", "unit": "percent", "is_revisable": False, "release_lag_days": 15, "release_timezone": "America/Sao_Paulo"},
        {"series_code": "13522", "name": "IPCA Acumulado 12 Meses", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "11426", "name": "IPCA Nucleo EX0", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "27838", "name": "IPCA Nucleo EX3", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "11427", "name": "IPCA Nucleo Medias Aparadas", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "27839", "name": "IPCA Nucleo Dupla Ponderacao", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "4466", "name": "IPCA Nucleo P55", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "21379", "name": "Indice Difusao IPCA", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "7478", "name": "IPCA-15 Variacao Mensal", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "188", "name": "INPC Mensal", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "189", "name": "IGP-M Mensal", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "190", "name": "IGP-DI Mensal", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "225", "name": "IPA-M Mensal", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "7446", "name": "IPC-S Semanal", "frequency": "W", "country": "BR", "unit": "percent"},
        {"series_code": "10764", "name": "IPC-Fipe Semanal", "frequency": "W", "country": "BR", "unit": "percent"},
        # ACTIVITY
        {"series_code": "22099", "name": "PIB Trimestral", "frequency": "Q", "country": "BR", "unit": "percent"},
        {"series_code": "24364", "name": "IBC-Br (proxy PIB mensal)", "frequency": "M", "country": "BR", "unit": "index"},
        {"series_code": "21859", "name": "Producao Industrial", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "1455", "name": "PMC Varejo Restrito", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "28473", "name": "PMC Varejo Ampliado", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "23987", "name": "PMS Receita Servicos", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "4393", "name": "ICC Confianca Consumidor", "frequency": "M", "country": "BR", "unit": "index"},
        {"series_code": "7343", "name": "ICE Confianca Empresarial", "frequency": "M", "country": "BR", "unit": "index"},
        {"series_code": "1344", "name": "Utilizacao Capacidade Instalada", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "28763", "name": "CAGED Emprego Formal", "frequency": "M", "country": "BR", "unit": "thousands"},
        {"series_code": "24369", "name": "PNAD Desemprego", "frequency": "M", "country": "BR", "unit": "percent"},
        # MONETARY & CREDIT
        {"series_code": "432", "name": "Meta Selic", "frequency": "D", "country": "BR", "unit": "percent"},
        {"series_code": "11", "name": "Selic Efetiva Diaria", "frequency": "D", "country": "BR", "unit": "percent"},
        {"series_code": "12", "name": "CDI Diario", "frequency": "D", "country": "BR", "unit": "percent"},
        {"series_code": "20539", "name": "Credito Total / PIB", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "21082", "name": "Inadimplencia PF", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "21083", "name": "Inadimplencia PJ", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "20714", "name": "Taxa Media Emprestimos", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "1824", "name": "Base Monetaria M1", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "1837", "name": "M2", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "1838", "name": "M3", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "1839", "name": "M4", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "1788", "name": "Base Monetaria", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        # EXTERNAL
        {"series_code": "22707", "name": "Balanca Comercial", "frequency": "M", "country": "BR", "unit": "USD_MM"},
        {"series_code": "22885", "name": "Saldo Transacoes Correntes", "frequency": "M", "country": "BR", "unit": "USD_MM"},
        {"series_code": "22918", "name": "Conta Corrente / PIB", "frequency": "Q", "country": "BR", "unit": "percent"},
        {"series_code": "22886", "name": "Investimento Direto no Pais", "frequency": "M", "country": "BR", "unit": "USD_MM"},
        {"series_code": "22888", "name": "Investimento Carteira Acoes", "frequency": "M", "country": "BR", "unit": "USD_MM"},
        {"series_code": "22889", "name": "Investimento Carteira Renda Fixa", "frequency": "M", "country": "BR", "unit": "USD_MM"},
        {"series_code": "13621", "name": "Reservas Internacionais", "frequency": "D", "country": "BR", "unit": "USD_MM"},
        {"series_code": "1", "name": "PTAX Compra", "frequency": "D", "country": "BR", "unit": "BRL"},
        {"series_code": "10813", "name": "PTAX Venda", "frequency": "D", "country": "BR", "unit": "BRL"},
        # FISCAL
        {"series_code": "5793", "name": "Resultado Primario Consolidado", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "5727", "name": "Resultado Nominal", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "4513", "name": "DLSP / PIB", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "13762", "name": "DBGG / PIB", "frequency": "M", "country": "BR", "unit": "percent"},
    ]


def _fred_series() -> list[dict]:
    """All 50 FRED US macro series."""
    return [
        # INFLATION
        {"series_code": "CPIAUCSL", "name": "CPI All Items SA", "frequency": "M", "country": "US", "unit": "index", "is_revisable": False, "release_lag_days": 13},
        {"series_code": "CPIAUCNS", "name": "CPI All Items NSA", "frequency": "M", "country": "US", "unit": "index"},
        {"series_code": "CPILFESL", "name": "CPI Core (Less Food & Energy)", "frequency": "M", "country": "US", "unit": "index"},
        {"series_code": "TRMMEANCPIM158SFRBCLE", "name": "CPI Trimmed Mean", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "MEDCPIM158SFRBCLE", "name": "CPI Median", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "STICKCPIM157SFRBATL", "name": "CPI Sticky", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "FLEXCPIM157SFRBATL", "name": "CPI Flexible", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "PCEPI", "name": "PCE Price Index", "frequency": "M", "country": "US", "unit": "index", "is_revisable": True},
        {"series_code": "PCEPILFE", "name": "PCE Core Price Index", "frequency": "M", "country": "US", "unit": "index", "is_revisable": True},
        {"series_code": "PPIACO", "name": "PPI All Commodities", "frequency": "M", "country": "US", "unit": "index"},
        {"series_code": "MICH", "name": "Michigan Inflation Expectations 1Y", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "T5YIE", "name": "5Y Breakeven Inflation", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "T10YIE", "name": "10Y Breakeven Inflation", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "T5YIFR", "name": "5Y5Y Forward Inflation", "frequency": "D", "country": "US", "unit": "percent"},
        # ACTIVITY & LABOR
        {"series_code": "GDPC1", "name": "Real GDP", "frequency": "Q", "country": "US", "unit": "USD_BN", "is_revisable": True},
        {"series_code": "PAYEMS", "name": "Nonfarm Payrolls", "frequency": "M", "country": "US", "unit": "thousands", "is_revisable": True, "release_lag_days": 5},
        {"series_code": "USPRIV", "name": "Private Nonfarm Payrolls", "frequency": "M", "country": "US", "unit": "thousands", "is_revisable": True},
        {"series_code": "UNRATE", "name": "Unemployment Rate U3", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "U6RATE", "name": "Unemployment Rate U6", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "CES0500000003", "name": "Average Hourly Earnings", "frequency": "M", "country": "US", "unit": "USD"},
        {"series_code": "JTSJOL", "name": "JOLTS Job Openings", "frequency": "M", "country": "US", "unit": "thousands"},
        {"series_code": "JTSQUR", "name": "JOLTS Quit Rate", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "ICSA", "name": "Initial Jobless Claims", "frequency": "W", "country": "US", "unit": "thousands"},
        {"series_code": "CCSA", "name": "Continuing Jobless Claims", "frequency": "W", "country": "US", "unit": "thousands"},
        {"series_code": "INDPRO", "name": "Industrial Production Index", "frequency": "M", "country": "US", "unit": "index", "is_revisable": True},
        {"series_code": "TCU", "name": "Capacity Utilization", "frequency": "M", "country": "US", "unit": "percent"},
        {"series_code": "RSAFS", "name": "Retail Sales Total", "frequency": "M", "country": "US", "unit": "USD_MM", "is_revisable": True},
        {"series_code": "RSFSXMV", "name": "Retail Sales Control Group", "frequency": "M", "country": "US", "unit": "USD_MM", "is_revisable": True},
        {"series_code": "HOUST", "name": "Housing Starts", "frequency": "M", "country": "US", "unit": "thousands"},
        {"series_code": "PERMIT", "name": "Building Permits", "frequency": "M", "country": "US", "unit": "thousands"},
        {"series_code": "PI", "name": "Personal Income", "frequency": "M", "country": "US", "unit": "USD_BN", "is_revisable": True},
        {"series_code": "PCE", "name": "Personal Consumption Expenditures", "frequency": "M", "country": "US", "unit": "USD_BN", "is_revisable": True},
        {"series_code": "UMCSENT", "name": "U. Michigan Consumer Sentiment", "frequency": "M", "country": "US", "unit": "index"},
        {"series_code": "CFNAI", "name": "Chicago Fed National Activity Index", "frequency": "M", "country": "US", "unit": "index"},
        # MONETARY & RATES
        {"series_code": "DFF", "name": "Effective Federal Funds Rate", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "SOFR", "name": "SOFR", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "DGS2", "name": "Treasury 2Y Yield", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "DGS5", "name": "Treasury 5Y Yield", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "DGS10", "name": "Treasury 10Y Yield", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "DGS30", "name": "Treasury 30Y Yield", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "DFII5", "name": "TIPS 5Y Real Yield", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "DFII10", "name": "TIPS 10Y Real Yield", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "WALCL", "name": "Fed Total Assets", "frequency": "W", "country": "US", "unit": "USD_MM"},
        {"series_code": "WTREGEN", "name": "Fed Treasury Holdings", "frequency": "W", "country": "US", "unit": "USD_MM"},
        {"series_code": "WSHOMCB", "name": "Fed MBS Holdings", "frequency": "W", "country": "US", "unit": "USD_MM"},
        {"series_code": "RRPONTSYD", "name": "ON RRP", "frequency": "D", "country": "US", "unit": "USD_BN"},
        {"series_code": "NFCI", "name": "Chicago Fed NFCI", "frequency": "W", "country": "US", "unit": "index"},
        # CREDIT
        {"series_code": "BAMLH0A0HYM2", "name": "High Yield OAS", "frequency": "D", "country": "US", "unit": "percent"},
        {"series_code": "BAMLC0A0CM", "name": "Investment Grade OAS", "frequency": "D", "country": "US", "unit": "percent"},
        # FISCAL
        {"series_code": "GFDEBTN", "name": "Federal Debt Total", "frequency": "Q", "country": "US", "unit": "USD_MM"},
        {"series_code": "GFDEGDQ188S", "name": "Federal Debt / GDP", "frequency": "Q", "country": "US", "unit": "percent"},
    ]


def _bcb_fx_flow_series() -> list[dict]:
    """BCB FX Flow series."""
    return [
        {"series_code": "22704", "name": "FX Flow Commercial", "frequency": "W", "country": "BR", "unit": "USD_MM"},
        {"series_code": "22705", "name": "FX Flow Financial", "frequency": "W", "country": "BR", "unit": "USD_MM"},
        {"series_code": "22706", "name": "FX Flow Total", "frequency": "W", "country": "BR", "unit": "USD_MM"},
        {"series_code": "12070", "name": "BCB Swap Stock", "frequency": "D", "country": "BR", "unit": "USD_MM"},
    ]


def _stn_fiscal_series() -> list[dict]:
    """STN Fiscal series (from BCB SGS)."""
    return [
        {"series_code": "5364", "name": "Primary Balance Central Govt Monthly", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "4513", "name": "Net Debt / GDP", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "13762", "name": "Gross Debt / GDP", "frequency": "M", "country": "BR", "unit": "percent"},
        {"series_code": "21864", "name": "Total Government Revenue", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "21865", "name": "Total Government Expenditure", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
        {"series_code": "7620", "name": "Social Security (RGPS) Deficit", "frequency": "M", "country": "BR", "unit": "BRL_MM"},
    ]


def _ibge_sidra_series() -> list[dict]:
    """IBGE SIDRA IPCA component series (MoM + Weight for each of 9 groups)."""
    groups = ["FOOD", "HOUSING", "HOUSEHOLD", "CLOTHING", "TRANSPORT",
              "HEALTH", "PERSONAL", "EDUCATION", "COMMUNICATION"]
    rows = []
    for g in groups:
        rows.append({"series_code": f"BR_IPCA_{g}_MOM", "name": f"IPCA {g.title()} MoM", "frequency": "M", "country": "BR", "unit": "percent"})
        rows.append({"series_code": f"BR_IPCA_{g}_WEIGHT", "name": f"IPCA {g.title()} Weight", "frequency": "M", "country": "BR", "unit": "percent"})
    return rows


def _cftc_series() -> list[dict]:
    """CFTC COT positioning series: 12 contracts x 4 categories = 48."""
    contracts = ["ES", "NQ", "YM", "TY", "US", "FV", "TU", "ED", "CL", "GC", "SI", "DX"]
    categories = ["DEALER", "ASSETMGR", "LEVERAGED", "OTHER"]
    rows = []
    for c in contracts:
        for cat in categories:
            rows.append({
                "series_code": f"CFTC_{c}_{cat}_NET",
                "name": f"CFTC {c} {cat.title()} Net Position",
                "frequency": "W",
                "country": "US",
                "unit": "contracts",
            })
    return rows


def _bcb_focus_series() -> list[dict]:
    """BCB Focus expectations (template entries -- actual year-specific series created at fetch time)."""
    indicators = ["IPCA", "SELIC", "PIB", "CAMBIO", "IGPM"]
    rows = []
    for ind in indicators:
        rows.append({"series_code": f"BR_FOCUS_{ind}_CY", "name": f"Focus {ind} Current Year", "frequency": "W", "country": "BR", "unit": "percent"})
        rows.append({"series_code": f"BR_FOCUS_{ind}_NY", "name": f"Focus {ind} Next Year", "frequency": "W", "country": "BR", "unit": "percent"})
    return rows


def main() -> None:
    session = sync_session_factory()
    try:
        # -- Seed data_sources -----------------------------------------------
        for ds in DATA_SOURCES:
            stmt = pg_insert(DataSource).values(**ds)
            stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
            session.execute(stmt)
        session.commit()
        ds_count = session.query(DataSource).count()
        print(f"Data sources: {ds_count} total in table.")

        # Build source_id lookup
        source_ids: dict[str, int] = {}
        for row in session.execute(select(DataSource.id, DataSource.name)):
            source_ids[row.name] = row.id

        # -- Build series catalogue ------------------------------------------
        catalogue: list[tuple[str, list[dict]]] = [
            ("BCB_SGS", _bcb_sgs_series()),
            ("FRED", _fred_series()),
            ("BCB_FX_FLOW", _bcb_fx_flow_series()),
            ("STN_FISCAL", _stn_fiscal_series()),
            ("IBGE_SIDRA", _ibge_sidra_series()),
            ("CFTC_COT", _cftc_series()),
            ("BCB_FOCUS", _bcb_focus_series()),
        ]

        inserted = 0
        for source_name, series_list in catalogue:
            sid = source_ids.get(source_name)
            if sid is None:
                print(f"  WARNING: data source '{source_name}' not found, skipping.")
                continue
            for s in series_list:
                defaults = {
                    "decimal_separator": ".",
                    "date_format": "YYYY-MM-DD",
                    "is_revisable": False,
                    "release_timezone": "UTC",
                    "is_active": True,
                }
                defaults.update(s)
                defaults["source_id"] = sid
                # Remove keys that are not columns
                for k in list(defaults.keys()):
                    if k == "release_lag_days" and defaults[k] is None:
                        del defaults[k]
                stmt = pg_insert(SeriesMetadata).values(**defaults)
                stmt = stmt.on_conflict_do_nothing(
                    constraint="uq_series_metadata_source_series"
                )
                result = session.execute(stmt)
                inserted += result.rowcount  # type: ignore[union-attr]
        session.commit()

        total = session.query(SeriesMetadata).count()
        print(f"Seeded {inserted} new series_metadata rows ({total} total in table).")

    finally:
        session.close()


if __name__ == "__main__":
    main()
