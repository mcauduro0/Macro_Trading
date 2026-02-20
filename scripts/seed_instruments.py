"""Seed the instruments table with all tradeable instruments.

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING on the unique ticker column.
Includes instrument_type and contract_specs per GUIA Etapa 2/10 specification.
Run: python scripts/seed_instruments.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.database import sync_engine, sync_session_factory
from src.core.models.instruments import Instrument


INSTRUMENTS = [
    # ── FX SPOT ──────────────────────────────────────────────────────────────
    {"ticker": "USDBRL", "name": "US Dollar / Brazilian Real Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "BR", "currency": "BRL", "exchange": "OTC"},
    {"ticker": "USDBRL_PTAX", "name": "PTAX Official Rate", "asset_class": "FX", "instrument_type": "SPOT", "country": "BR", "currency": "BRL", "exchange": "BCB"},
    {"ticker": "EURUSD", "name": "Euro / US Dollar Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "US", "currency": "USD", "exchange": "OTC"},
    {"ticker": "USDJPY", "name": "US Dollar / Japanese Yen Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "JP", "currency": "JPY", "exchange": "OTC"},
    {"ticker": "GBPUSD", "name": "British Pound / US Dollar Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "GB", "currency": "USD", "exchange": "OTC"},
    {"ticker": "USDCHF", "name": "US Dollar / Swiss Franc Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "CH", "currency": "CHF", "exchange": "OTC"},
    {"ticker": "DXY", "name": "US Dollar Index", "asset_class": "FX", "instrument_type": "INDEX", "country": "US", "currency": "USD", "exchange": "ICE"},
    {"ticker": "USDMXN", "name": "US Dollar / Mexican Peso Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "MX", "currency": "MXN", "exchange": "OTC"},
    {"ticker": "USDCNY", "name": "US Dollar / Chinese Yuan Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "CN", "currency": "CNY", "exchange": "OTC"},
    {"ticker": "USDCLP", "name": "US Dollar / Chilean Peso Spot", "asset_class": "FX", "instrument_type": "SPOT", "country": "CL", "currency": "CLP", "exchange": "OTC"},

    # ── EQUITY INDICES ───────────────────────────────────────────────────────
    {"ticker": "IBOVESPA", "name": "Ibovespa Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "country": "BR", "currency": "BRL", "exchange": "B3"},
    {"ticker": "SP500", "name": "S&P 500 Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "country": "US", "currency": "USD", "exchange": "CME"},
    {"ticker": "VIX", "name": "CBOE Volatility Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "country": "US", "currency": "USD", "exchange": "CBOE"},
    {"ticker": "NASDAQ", "name": "NASDAQ Composite Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "country": "US", "currency": "USD", "exchange": "NASDAQ"},
    {"ticker": "RUSSELL2000", "name": "Russell 2000 Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "country": "US", "currency": "USD", "exchange": "CME"},

    # ── COMMODITIES ──────────────────────────────────────────────────────────
    {
        "ticker": "GOLD", "name": "Gold Futures (front month)", "asset_class": "COMMODITIES",
        "instrument_type": "FUTURE", "country": "US", "currency": "USD", "exchange": "CME",
        "contract_specs": {"multiplier": 100, "tick_size": 0.10, "tick_value": 10.0, "margin": 11000, "settlement_type": "physical"},
    },
    {
        "ticker": "OIL_WTI", "name": "WTI Crude Oil Futures", "asset_class": "COMMODITIES",
        "instrument_type": "FUTURE", "country": "US", "currency": "USD", "exchange": "CME",
        "contract_specs": {"multiplier": 1000, "tick_size": 0.01, "tick_value": 10.0, "margin": 7500, "settlement_type": "physical"},
    },
    {
        "ticker": "OIL_BRENT", "name": "Brent Crude Oil Futures", "asset_class": "COMMODITIES",
        "instrument_type": "FUTURE", "country": "GB", "currency": "USD", "exchange": "ICE",
        "contract_specs": {"multiplier": 1000, "tick_size": 0.01, "tick_value": 10.0, "margin": 7500, "settlement_type": "cash"},
    },
    {
        "ticker": "SOYBEAN", "name": "Soybean Futures", "asset_class": "COMMODITIES",
        "instrument_type": "FUTURE", "country": "US", "currency": "USD", "exchange": "CME",
        "contract_specs": {"multiplier": 5000, "tick_size": 0.25, "tick_value": 12.50, "margin": 4400, "settlement_type": "physical"},
    },
    {
        "ticker": "CORN", "name": "Corn Futures", "asset_class": "COMMODITIES",
        "instrument_type": "FUTURE", "country": "US", "currency": "USD", "exchange": "CME",
        "contract_specs": {"multiplier": 5000, "tick_size": 0.25, "tick_value": 12.50, "margin": 1650, "settlement_type": "physical"},
    },
    {
        "ticker": "COPPER", "name": "Copper Futures", "asset_class": "COMMODITIES",
        "instrument_type": "FUTURE", "country": "US", "currency": "USD", "exchange": "CME",
        "contract_specs": {"multiplier": 25000, "tick_size": 0.0005, "tick_value": 12.50, "margin": 7700, "settlement_type": "physical"},
    },
    {"ticker": "IRON_ORE_PROXY", "name": "Iron Ore (Vale proxy)", "asset_class": "COMMODITIES", "instrument_type": "ETF", "country": "BR", "currency": "BRL", "exchange": "B3"},

    # ── ETFs ─────────────────────────────────────────────────────────────────
    {"ticker": "EWZ", "name": "iShares MSCI Brazil ETF", "asset_class": "EQUITY_INDEX", "instrument_type": "ETF", "country": "US", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "TIP_ETF", "name": "iShares TIPS Bond ETF", "asset_class": "INFLATION_US", "instrument_type": "ETF", "country": "US", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "TLT_ETF", "name": "iShares 20+ Year Treasury Bond ETF", "asset_class": "RATES_US", "instrument_type": "ETF", "country": "US", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "HYG_ETF", "name": "iShares iBoxx HY Corporate Bond ETF", "asset_class": "SOVEREIGN_CREDIT", "instrument_type": "ETF", "country": "US", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "EMB_ETF", "name": "iShares JP Morgan EM Bond ETF", "asset_class": "SOVEREIGN_CREDIT", "instrument_type": "ETF", "country": "US", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "LQD_ETF", "name": "iShares iBoxx IG Corporate Bond ETF", "asset_class": "SOVEREIGN_CREDIT", "instrument_type": "ETF", "country": "US", "currency": "USD", "exchange": "NYSE"},
]


def main() -> None:
    session = sync_session_factory()
    try:
        stmt = pg_insert(Instrument).values(INSTRUMENTS)
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker"])
        result = session.execute(stmt)
        session.commit()
        count = result.rowcount  # type: ignore[union-attr]
        total = session.query(Instrument).count()
        print(f"Seeded {count} new instruments ({total} total in table).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
