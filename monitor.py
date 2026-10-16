"""보유/관심 종목 급변 알림 + 매일 오전 9시 금·비트코인·이더리움 시세 브리핑 (텔레그램).

사용법
  python monitor.py                  장 시간 동안 1분마다 감시 (GitHub Actions에서 실행)
  python monitor.py --briefing-now   시세 브리핑을 지금 바로 1회 전송
  python monitor.py --check          관심 종목 현재 시세만 출력 (알림 없음)

알림 규칙
  1) 전일 종가 대비 ±3%, ±6%, ±9% ... 단계를 처음 넘을 때마다 1회
  2) 최근 10분 안에 3% 이상 급등/급락 (같은 방향은 30분에 한 번만)
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "state.json"

DAILY_STEP = 3.0          # 전일 대비 알림 단계 (%)
SURGE_PCT = 3.0           # 단기 급변 기준 (%)
SURGE_WINDOW = 10 * 60    # 단기 급변 확인 구간 (초)
SURGE_COOLDOWN = 30 * 60  # 같은 종목·같은 방향 재알림 간격 (초)
POLL_SECONDS = 60
LOOKAHEAD = timedelta(minutes=100)  # 장 시작 전 이 시간 안이면 기다림

MARKETS = {
    # 이름: (시간대, 개장, 마감)
    "KR": (KST, (9, 0), (15, 30)),
    "US": (NY, (9, 30), (16, 0)),
}


# ---------------------------------------------------------------- 설정
def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def load_watchlist():
    """WATCHLIST 환경변수(JSON)가 있으면 그것을, 없으면 watchlist.json을 사용."""
    raw = os.environ.get("WATCHLIST") or (ROOT / "watchlist.json").read_text(encoding="utf-8")
    stocks = json.loads(raw)["stocks"]
    for s in stocks:
        s["market"] = "KR" if s["code"].isdigit() else "US"
    return stocks


# ---------------------------------------------------------------- 시세
def http_json(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def num(s):
    return float(str(s).replace(",", ""))


def fetch_quotes(stocks):
    """{code: {name, price, ratio, open}} — 네이버 실시간 시세."""
    out = {}
    groups = {"domestic": [s for s in stocks if s["market"] == "KR"],
              "worldstock": [s for s in stocks if s["market"] == "US"]}
    for kind, items in groups.items():
        for i in range(0, len(items), 20):
            chunk = items[i:i + 20]
            codes = ",".join(s["code"] for s in chunk)
            try:
                datas = http_json(f"https://polling.finance.naver.com/api/realtime/{kind}/stock/{codes}")["datas"]
            except Exception as e:
                print(f"[시세 오류] {kind} {codes}: {e}")
                continue
            for d in datas:
                code = d.get("itemCode") or d.get("reutersCode")
                out[code] = {
                    "name": d.get("stockName"),
                    "price": num(d.get("closePriceRaw") or d["closePrice"]),
                    "ratio": num(d.get("fluctuationsRatioRaw") or d["fluctuationsRatio"]),
                    "open": d.get("marketStatus") == "OPEN",
                }
    return out


def market_index(category, code):
    r = http_json(f"https://m.stock.naver.com/front-api/marketIndex/productDetail?category={category}&reutersCode={code}")["result"]
    return num(r["closePrice"]), num(r["fluctuationsRatio"])


def fmt_price(price, market):
    return f"{price:,.0f}원" if market == "KR" else f"${price:,.2f}"


def fmt_pct(p):
    return f"{p:+.2f}%"


# ---------------------------------------------------------------- 텔레그램
def send(text):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    print("─" * 40 + "\n" + text)
    if not token or not chat:
        print("(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없어 화면에만 출력)")
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        http_json(f"https://api.telegram.org/bot{token}/sendMessage", data)
    except Exception as e:
        print(f"[텔레그램 전송 실패] {e}")


# ---------------------------------------------------------------- 브리핑
def briefing():
    now = datetime.now(KST)
    lines = [f"☀️ <b>{now:%m/%d} ({'월화수목금토일'[now.weekday()]}) 오전 시세 브리핑</b>", ""]
    try:
        p, r = market_index("metals", "GCcv1")
        lines.append(f"🥇 국제 금  ${p:,.1f}/oz ({fmt_pct(r)})")
    except Exception as e:
        lines.append(f"🥇 국제 금  조회 실패 ({e})")
    try:
        p, r = market_index("metals", "M04020000")
        lines.append(f"🥇 국내 금(KRX)  {p:,.0f}원/g ({fmt_pct(r)}, 1돈 약 {p * 3.75:,.0f}원)")
    except Exception as e:
        lines.append(f"🥇 국내 금  조회 실패 ({e})")
    try:
        for t in http_json("https://api.upbit.com/v1/ticker?markets=KRW-BTC,KRW-ETH"):
            icon, name = ("₿", "비트코인") if t["market"] == "KRW-BTC" else ("Ξ", "이더리움")
            lines.append(f"{icon} {name}  {t['trade_price']:,.0f}원 ({fmt_pct(t['signed_change_rate'] * 100)})")
    except Exception as e:
        lines.append(f"₿ 코인  조회 실패 ({e})")
    try:
        p, r = market_index("exchange", "FX_USDKRW")
        lines.append(f"💵 원/달러  {p:,.2f}원 ({fmt_pct(r)})")
    except Exception:
        pass
    lines += ["", "<i>코인 등락률은 업비트 전일 09시 대비</i>"]
    send("\n".join(lines))


# ---------------------------------------------------------------- 상태
def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def market_now(market):
    return datetime.now(MARKETS[market][0])


def is_open(market, now=None):
    tz, (oh, om), (ch, cm) = MARKETS[market]
    now = now or datetime.now(tz)
    return now.weekday() < 5 and (oh, om) <= (now.hour, now.minute) < (ch, cm)


def opens_soon(market):
    now = market_now(market)
    return any(is_open(market, now + timedelta(minutes=m)) for m in range(0, int(LOOKAHEAD.total_seconds() // 60), 5))


# ---------------------------------------------------------------- 알림 판단
def check_alerts(stock, q, state, history, now_ts):
    code, market = stock["code"], stock["market"]
    name = stock.get("name") or q["name"]
    price, ratio = q["price"], q["ratio"]
    label = f"<b>{name}</b> ({code.split('.')[0]})"
    day = market_now(market).strftime("%Y-%m-%d")

    # 1) 전일 대비 단계 돌파
    daily = state.setdefault("daily", {})
    for k in list(daily):
        if k < (datetime.now(KST) - timedelta(days=3)).strftime("%Y-%m-%d"):
            del daily[k]
    rec = daily.setdefault(day, {}).setdefault(code, {"up": 0, "down": 0})
    level = int(abs(ratio) // DAILY_STEP)
    side = "up" if ratio > 0 else "down"
    if level >= 1 and level > rec[side]:
        rec[side] = level
        icon = "📈" if side == "up" else "📉"
        send(f"{icon} {label} 전일 대비 <b>{'+' if side == 'up' else '-'}{level * DAILY_STEP:.0f}%</b> 돌파\n"
             f"현재가 {fmt_price(price, market)} ({fmt_pct(ratio)})")

    # 2) 최근 10분 급변
    h = history.setdefault(code, deque())
    h.append((now_ts, price))
    while h and h[0][0] < now_ts - SURGE_WINDOW:
        h.popleft()
    low, high = min(p for _, p in h), max(p for _, p in h)
    cool = state.setdefault("surge", {})
    for direction, base, change in (("up", low, (price - low) / low * 100),
                                    ("down", high, (price - high) / high * 100)):
        hit = change >= SURGE_PCT if direction == "up" else change <= -SURGE_PCT
        key = f"{code}:{direction}"
        if hit and now_ts - cool.get(key, -SURGE_COOLDOWN) >= SURGE_COOLDOWN:
            cool[key] = now_ts
            icon = "🚀 급등" if direction == "up" else "⚠️ 급락"
            send(f"{icon} {label} 최근 10분 <b>{fmt_pct(change)}</b>\n"
                 f"{fmt_price(base, market)} → {fmt_price(price, market)} (전일 대비 {fmt_pct(ratio)})")


# ---------------------------------------------------------------- 메인 루프
def run(budget_minutes):
    stocks = load_watchlist()
    markets = {s["market"] for s in stocks}
    state = load_state()
    history = {}
    deadline = time.time() + budget_minutes * 60
    print(f"감시 시작: {len(stocks)}종목, 최대 {budget_minutes}분")

    while time.time() < deadline:
        now = datetime.now(KST)
        today = now.strftime("%Y-%m-%d")
        briefing_due = now.weekday() < 5 and 9 <= now.hour < 12 and state.get("briefing_date") != today
        if briefing_due:
            briefing()
            state["briefing_date"] = today
            save_state(state)

        open_markets = {m for m in markets if is_open(m)}
        if open_markets:
            targets = [s for s in stocks if s["market"] in open_markets]
            quotes = fetch_quotes(targets)
            now_ts = time.time()
            for s in targets:
                q = quotes.get(s["code"])
                if q and q["open"]:  # 휴장일·거래정지는 건너뜀
                    check_alerts(s, q, state, history, now_ts)
            save_state(state)
        else:
            waiting_briefing = now.weekday() < 5 and now.hour < 9 and (now + LOOKAHEAD).hour >= 9
            if not waiting_briefing and not any(opens_soon(m) for m in markets):
                print("열려 있거나 곧 열릴 장이 없어 종료")
                break
        time.sleep(max(1, POLL_SECONDS - (time.time() % POLL_SECONDS)))
    save_state(state)


def check():
    stocks = load_watchlist()
    quotes = fetch_quotes(stocks)
    for s in stocks:
        q = quotes.get(s["code"])
        if q:
            print(f"{s.get('name') or q['name']:<14} {fmt_price(q['price'], s['market']):>14} {fmt_pct(q['ratio']):>8}"
                  f"  {'장중' if q['open'] else '장마감'}")
        else:
            print(f"{s.get('name', '')} ({s['code']}) 시세 없음 — 종목코드를 확인하세요")


if __name__ == "__main__":
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefing-now", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--budget", type=int, default=345, help="최대 실행 시간(분), GitHub Actions 한도 6시간")
    a = ap.parse_args()
    if a.briefing_now:
        briefing()
    elif a.check:
        check()
    else:
        run(a.budget)
