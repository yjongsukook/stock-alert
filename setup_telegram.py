"""텔레그램 봇 연결 도우미.

1) 텔레그램에서 @BotFather → /newbot → 봇 토큰 받기
2) .env 파일에 TELEGRAM_BOT_TOKEN=받은토큰 입력
3) 만든 봇과 대화창을 열고 아무 메시지나 보내기 (예: 안녕)
4) python setup_telegram.py  → chat_id를 찾아 .env에 저장하고 테스트 메시지 전송
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path(__file__).parent / ".env"


def read_env():
    if not ENV.exists():
        return {}
    pairs = (l.split("=", 1) for l in ENV.read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs}


def call(token, method, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
        return json.loads(r.read())


env = read_env()
token = env.get("TELEGRAM_BOT_TOKEN")
if not token:
    raise SystemExit(".env 에 TELEGRAM_BOT_TOKEN 을 먼저 입력하세요 (.env.example 참고)")

updates = call(token, "getUpdates")["result"]
chats = [u["message"]["chat"] for u in updates if "message" in u]
if not chats:
    raise SystemExit("봇에게 온 메시지가 없습니다. 텔레그램에서 봇에게 아무 메시지나 보낸 뒤 다시 실행하세요.")

chat_id = str(chats[-1]["id"])
env["TELEGRAM_CHAT_ID"] = chat_id
ENV.write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")
call(token, "sendMessage", chat_id=chat_id, text="✅ 주가 알림 봇 연결 완료!")
print(f"chat_id {chat_id} 를 .env 에 저장했고 테스트 메시지를 보냈습니다.")
