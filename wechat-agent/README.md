# 微信 Agent

这是一个微信公众号消息接口版 Agent。手机微信关注你的公众号或测试号后，给公众号发文字消息，就会转发给大模型并返回微信聊天回复。

## 1. 准备配置

复制配置模板：

```powershell
copy .env.example .env
```

编辑 `.env`：

```env
WECHAT_TOKEN=自己随便设置一个复杂字符串
LLM_API_KEY=你的模型 API Key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

`WECHAT_TOKEN` 要和微信公众号后台服务器配置里的 Token 完全一致。

## 2. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 3. 本地启动

```powershell
python server.py
```

默认监听：

```text
http://127.0.0.1:8000/wechat
```

## 4. 暴露公网地址

微信公众号后台不能访问你的 `127.0.0.1`，需要公网 HTTPS 地址。开发测试可以用内网穿透工具，例如：

```powershell
ngrok http 8000
```

拿到类似下面的地址：

```text
https://xxxx.ngrok-free.app/wechat
```

## 5. 配置微信公众号

在微信公众号平台或测试号里启用服务器配置：

- URL：你的公网地址，结尾要带 `/wechat`
- Token：`.env` 里的 `WECHAT_TOKEN`
- EncodingAESKey：随机生成或明文模式按后台要求填写
- 消息加解密方式：测试时建议先用明文模式

保存通过后，用手机微信给公众号发消息即可聊天。

## 注意

不要用个人微信号扫码登录式机器人做长期服务，容易违反平台规则并导致账号异常。公众号或企业微信接口更稳。
