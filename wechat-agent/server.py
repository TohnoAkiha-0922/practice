import hashlib
import html
import os
import time
from collections import defaultdict, deque
from xml.etree import ElementTree

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from openai import OpenAI


load_dotenv()

WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
SYSTEM_PROMPT = os.getenv(
    "AGENT_SYSTEM_PROMPT",
    "你是一个在微信里聊天的中文助手，回答简洁、自然、有帮助。",
)

app = Flask(__name__)
client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

# Keep a small in-memory context per WeChat user. Restarting the service clears it.
histories = defaultdict(lambda: deque(maxlen=12))


CHAT_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>微信 Agent</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f5f7;
      color: #1f2329;
    }
    .app {
      height: 100dvh;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    header {
      padding: 14px 16px 10px;
      background: #ffffff;
      border-bottom: 1px solid #e6e8eb;
      font-weight: 700;
      text-align: center;
    }
    #messages {
      padding: 14px;
      overflow-y: auto;
    }
    .row {
      display: flex;
      margin: 10px 0;
    }
    .row.user { justify-content: flex-end; }
    .bubble {
      max-width: 78%;
      padding: 10px 12px;
      border-radius: 8px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 15px;
      box-shadow: 0 1px 1px rgba(0,0,0,.04);
    }
    .agent .bubble { background: #ffffff; }
    .user .bubble { background: #95ec69; }
    form {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 10px;
      background: #ffffff;
      border-top: 1px solid #e6e8eb;
    }
    textarea {
      min-height: 42px;
      max-height: 120px;
      resize: none;
      border: 1px solid #d8dde3;
      border-radius: 8px;
      padding: 10px;
      font-size: 16px;
      outline: none;
    }
    button {
      width: 64px;
      border: 0;
      border-radius: 8px;
      background: #07c160;
      color: white;
      font-weight: 700;
      font-size: 16px;
    }
    button:disabled { opacity: .55; }
  </style>
</head>
<body>
  <div class="app">
    <header>微信 Agent</header>
    <main id="messages"></main>
    <form id="form">
      <textarea id="text" rows="1" placeholder="发消息..."></textarea>
      <button id="send" type="submit">发送</button>
    </form>
  </div>
  <script>
    const messages = document.querySelector("#messages");
    const form = document.querySelector("#form");
    const text = document.querySelector("#text");
    const send = document.querySelector("#send");
    const sessionId = localStorage.getItem("wechat_agent_session") || crypto.randomUUID();
    localStorage.setItem("wechat_agent_session", sessionId);

    function addMessage(role, content) {
      const row = document.createElement("div");
      row.className = `row ${role}`;
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = content;
      row.appendChild(bubble);
      messages.appendChild(row);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    addMessage("agent", "你好，我是你的手机微信 Agent。直接发消息给我。");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const content = text.value.trim();
      if (!content) return;
      text.value = "";
      addMessage("user", content);
      const waiting = addMessage("agent", "正在想...");
      send.disabled = true;
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "bypass-tunnel-reminder": "true"
          },
          body: JSON.stringify({ session_id: sessionId, message: content })
        });
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          throw new Error("隧道提示页拦截了接口请求");
        }
        const data = await res.json();
        waiting.textContent = data.reply || data.error || "没有拿到回复。";
      } catch (error) {
        waiting.textContent = "连接失败：请刷新页面，确认已通过 localtunnel 的 IP 验证，再试一次。";
      } finally {
        send.disabled = false;
        text.focus();
      }
    });
  </script>
</body>
</html>"""


def check_signature(signature: str, timestamp: str, nonce: str) -> bool:
    if not WECHAT_TOKEN or not signature or not timestamp or not nonce:
        return False
    raw = "".join(sorted([WECHAT_TOKEN, timestamp, nonce]))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return digest == signature


def parse_wechat_xml(body: bytes) -> dict:
    root = ElementTree.fromstring(body)
    return {child.tag: child.text or "" for child in root}


def text_reply(to_user: str, from_user: str, content: str) -> str:
    safe_content = html.escape(content[:1800])
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content>{safe_content}</Content>
</xml>"""


def call_agent(user_id: str, user_text: str) -> str:
    history = histories[user_id]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
        timeout=12,
    )
    answer = response.choices[0].message.content or "我刚才没组织好语言，你再发一次。"

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": answer})
    return answer


@app.get("/")
def index():
    return CHAT_PAGE


@app.get("/chat")
def chat_page():
    return CHAT_PAGE


@app.post("/api/chat")
def browser_chat():
    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id") or request.remote_addr or "browser")
    user_text = str(data.get("message") or "").strip()
    if not user_text:
        return jsonify({"error": "消息不能为空"}), 400
    try:
        return jsonify({"reply": call_agent(f"web:{session_id}", user_text)})
    except Exception as exc:
        return jsonify({"error": f"Agent 暂时没连上模型：{exc}"}), 500


@app.get("/wechat")
def verify_server():
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    echostr = request.args.get("echostr", "")

    if check_signature(signature, timestamp, nonce):
        return echostr
    abort(403)


@app.post("/wechat")
def receive_message():
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    if not check_signature(signature, timestamp, nonce):
        abort(403)

    try:
        msg = parse_wechat_xml(request.data)
    except ElementTree.ParseError:
        abort(400)

    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")
    msg_type = msg.get("MsgType", "")

    if msg_type == "event" and msg.get("Event") == "subscribe":
        return text_reply(from_user, to_user, "你好，我是你的微信 Agent。直接发消息给我就可以聊天。")

    if msg_type != "text":
        return text_reply(from_user, to_user, "我现在先支持文字聊天，你发文字给我就行。")

    user_text = msg.get("Content", "").strip()
    if not user_text:
        return text_reply(from_user, to_user, "你刚才发的是空消息。")

    try:
        answer = call_agent(from_user, user_text)
    except Exception as exc:
        answer = f"Agent 暂时没连上模型：{exc}"

    return text_reply(from_user, to_user, answer)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    if not WECHAT_TOKEN:
        raise RuntimeError("请先在 .env 里设置 WECHAT_TOKEN")
    if not LLM_API_KEY:
        raise RuntimeError("请先在 .env 里设置 LLM_API_KEY")
    app.run(host="0.0.0.0", port=port)
