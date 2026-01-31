#!/usr/bin/env python3
"""
Dedupe TradeHistory records that were accidentally recorded multiple times.

Default behavior is dry-run for master trades only.

Usage:
  python scripts/dedupe_trade_history.py
  python scripts/dedupe_trade_history.py --apply
  python scripts/dedupe_trade_history.py --apply --all-users
  python scripts/dedupe_trade_history.py --apply --window-seconds 10
"""

import argparse
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from models import TradeHistory  # noqa: E402


def _normalize_exchange_from_node(node_name: str) -> str:
    """Map node_name to a stable exchange key for master trades."""
    if not node_name:
        return "BINANCE"
    upper = node_name.upper()
    if "(" in upper and ")" in upper:
        inside = upper.split("(", 1)[1].split(")", 1)[0].strip()
        if inside.startswith("BINANCE"):
            return "BINANCE"
        return inside
    if upper.startswith("MASTER"):
        return "BINANCE"
    return upper


def _trade_key(trade: TradeHistory, master_only: bool) -> tuple:
    user_key = trade.user_id if trade.user_id is not None else "master"
    pnl_key = round(float(trade.pnl or 0), 2)
    base = (user_key, trade.symbol, trade.side, pnl_key)
    if trade.user_id is None and master_only:
        return base + (_normalize_exchange_from_node(trade.node_name),)
    return base + ((trade.node_name or "").upper(),)


def dedupe_trades(window_seconds: int, apply_changes: bool, master_only: bool) -> int:
    window = timedelta(seconds=window_seconds)
    query = TradeHistory.query
    if master_only:
        query = query.filter(TradeHistory.user_id.is_(None))
    trades = query.order_by(TradeHistory.close_time.asc(), TradeHistory.id.asc()).all()

    seen = {}
    duplicates = []
    for trade in trades:
        key = _trade_key(trade, master_only)
        last_trade = seen.get(key)
        if last_trade and (trade.close_time - last_trade.close_time) <= window:
            duplicates.append(trade)
        else:
            seen[key] = trade

    if not duplicates:
        print("No duplicates found.")
        return 0

    print(f"Found {len(duplicates)} duplicate trades.")
    if apply_changes:
        for trade in duplicates:
            db.session.delete(trade)
        db.session.commit()
        print("Duplicates removed.")
    else:
        print("Dry-run mode: no changes applied. Use --apply to delete.")
    return len(duplicates)


def main():
    parser = argparse.ArgumentParser(description="Dedupe TradeHistory rows")
    parser.add_argument("--apply", action="store_true", help="Delete duplicates")
    parser.add_argument("--all-users", action="store_true", help="Include slave/user trades")
    parser.add_argument("--window-seconds", type=int, default=10, help="Time window for duplicates")
    args = parser.parse_args()

    with app.app_context():
        dedupe_trades(
            window_seconds=max(1, args.window_seconds),
            apply_changes=args.apply,
            master_only=not args.all_users
        )


if __name__ == "__main__":
    main()
