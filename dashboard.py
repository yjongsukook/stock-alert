"""관심 종목·금·코인 시세 대시보드.  python dashboard.py → http://localhost:8010"""
import json
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import monitor as m

ROOT = Path(__file__).parent


def snapshot():
    stocks = m.load_watchlist()
    quotes = m.fetch_quotes(stocks)
    rows = []
    for s in stocks:
        q = quotes.get(s["code"])
        if q:
            rows.append({"code": s["code"], "name": s.get("name") or q["name"], "market": s["market"],
                         "price": m.fmt_price(q["price"], s["market"]), "ratio": q["ratio"], "open": q["open"]})
    assets = []
    for label, cat, code, fmt in (("국제 금", "metals", "GCcv1", "${:,.1f}/oz"),
                                  ("국내 금 (KRX)", "metals", "M04020000", "{:,.0f}원/g"),
                                  ("원/달러", "exchange", "FX_USDKRW", "{:,.2f}원")):
        try:
            p, r = m.market_index(cat, code)
            assets.append({"name": label, "price": fmt.format(p), "ratio": r})
        except Exception:
            pass
    try:
        for t in m.http_json("https://api.upbit.com/v1/ticker?markets=KRW-BTC,KRW-ETH"):
            assets.append({"name": "비트코인" if t["market"] == "KRW-BTC" else "이더리움",
                           "price": f"{t['trade_price']:,.0f}원", "ratio": t["signed_change_rate"] * 100})
    except Exception:
        pass
    return {"stocks": rows, "assets": assets}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "web"), **kw)

    def do_GET(self):
        if self.path.startswith("/api/data"):
            body = json.dumps(snapshot(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    m.load_env()
    url = "http://localhost:8010"
    print(f"대시보드: {url}  (종료: Ctrl+C)")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", 8010), Handler).serve_forever()
