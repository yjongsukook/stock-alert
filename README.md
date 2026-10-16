# 내 주식 알림

- **급변 알림**: 보유·관심 종목이 ① 전일 대비 ±3%·±6%·±9%…를 처음 넘을 때, ② 최근 10분 안에 3% 이상 움직일 때 텔레그램으로 알림
- **아침 브리핑**: 평일 오전 9시(KST)에 국제 금·국내 금·비트코인·이더리움·원/달러 시세 알림
- **대시보드**: `python dashboard.py` → http://localhost:8010

시세 출처: 국내·미국 주식과 금·환율은 네이버 증권(국내 실시간, 국제 금 약 10분 지연), 코인은 업비트(원화).

## 1. 종목 등록 — `watchlist.json`

```json
{"stocks": [
  {"code": "005930", "name": "삼성전자"},
  {"code": "AAPL.O", "name": "애플"}
]}
```
국내는 6자리 종목코드, 미국은 나스닥 `티커.O`, 뉴욕증권거래소 `티커.N` (예: `TSLA.O`, `KO.N`).
`python monitor.py --check` 로 코드가 맞는지 확인할 수 있습니다.

## 2. 텔레그램 봇 연결

1. 텔레그램에서 **@BotFather** → `/newbot` → 봇 토큰 받기
2. `.env.example` 을 `.env` 로 복사하고 `TELEGRAM_BOT_TOKEN=` 뒤에 토큰 붙여넣기
3. 방금 만든 봇과 대화창을 열어 아무 메시지나 보내기
4. `python setup_telegram.py` → chat_id 저장 + 테스트 메시지 수신 확인
5. `python monitor.py --briefing-now` → 브리핑이 휴대폰으로 오는지 확인

## 3. GitHub Actions로 자동 실행 (PC가 꺼져 있어도 동작)

1. GitHub에서 새 저장소 생성 (**Public 권장** — Actions 무료 시간 제한이 없음. 종목 목록·토큰은 저장소에 올라가지 않고 Secrets에만 저장됨)
2. 이 폴더를 그 저장소로 push
3. 저장소 **Settings → Secrets and variables → Actions → New repository secret** 에 3개 등록
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — `.env` 의 값
   - `WATCHLIST` — `watchlist.json` 내용 전체
4. **Actions → 주가 감시 → Run workflow → briefing** 으로 한 번 실행해 텔레그램 수신 확인

일정 (평일): 08:30 시작해 09시 브리핑 후 국내장 감시 → 13:30 예약분이 이어받아 15:30 마감까지 → 22:00·03:00 미국장 감시(미국 종목이 있을 때만).
GitHub 예약 실행은 몇 분씩 늦게 시작될 수 있어 장 시작보다 일찍 띄워 둡니다.
종목을 바꾸면 `WATCHLIST` Secret도 같이 수정하세요.
