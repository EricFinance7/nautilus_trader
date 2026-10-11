"""v2.0.0rc6: write Dukascopy QuoteTicks to a NautilusTrader ParquetDataCatalog in a scratch dir, read back, verify."""
import json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _dukascopy_loader import load_all_ticks
from nautilus_trader.model import Price, Quantity, QuoteTick, Venue
from nautilus_trader.persistence import ParquetDataCatalog
from nautilus_trader.testkit.providers import TestInstrumentProvider

inst = TestInstrumentProvider.default_fx_ccy("EUR/USD", Venue("SIM"))
raw = load_all_ticks()
ticks = [QuoteTick(inst.id, Price(r["bid"], 5), Price(r["ask"], 5), Quantity.from_int(1_000_000),
                   Quantity.from_int(1_000_000), r["ts_ms"] * 1_000_000, r["ts_ms"] * 1_000_000) for r in raw]
root = Path(tempfile.mkdtemp(prefix="nt_catalog_"))
try:
    cat = ParquetDataCatalog(str(root))
    cat.write_instruments([inst])
    cat.write_quote_ticks(ticks)
    back = cat.query_quote_ticks(identifiers=[inst.id.value], start=ticks[0].ts_event, end=ticks[-1].ts_event + 1)
    size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    ok = len(back) == len(ticks) and all(a.bid_price == b.bid_price and a.ask_price == b.ask_price
                                         and a.ts_event == b.ts_event for a, b in zip(ticks, back))
    print(json.dumps({"written": len(ticks), "read_back": len(back), "exact_match": ok,
                      "catalog_bytes": size, "bytes_per_tick": round(size / len(ticks), 1)}, indent=2))
finally:
    shutil.rmtree(root, ignore_errors=True)
