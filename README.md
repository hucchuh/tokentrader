# TokenTrader

TokenTrader 是一个「模型 Token 兑换与任务执行撮合」项目原型。现在包含：

- 交易撮合引擎（价格/质量/时延/可靠性评分）；
- 邮箱注册 + 登录会话；
- 一个可直接打开的 Web 前端交易台（下单报价、执行模拟）。

## 为什么这个方向可行

你的想法是对的：把“闲置 token”变成执行力供给，通过任务赚取内部 `token_credit`，再兑换到更贵模型能力。这个模式本质是 **执行力市场 + 统一清算单位**，可以避免直接互换不同供应商 token 的复杂性。

## 当前功能

- ✅ 用户邮箱注册（SQLite 持久化）
- ✅ 用户邮箱登录（会话 token）
- ✅ 任务报价（按预算 + 质量 + 时延自动排序）
- ✅ 模拟执行（选择 provider/model 进行执行）
- ✅ 前端控制台（现代化卡片 UI）

## 快速启动（Web）

```bash
PYTHONPATH=src python -m tokentrader.server
```

打开浏览器访问：

- `http://127.0.0.1:8080`

## 目录结构

- `src/tokentrader/engine.py`：撮合评分逻辑。
- `src/tokentrader/service.py`：用户注册登录、会话、报价和执行服务。
- `src/tokentrader/server.py`：HTTP API + 静态资源服务。
- `src/tokentrader/web/`：前端页面与样式。
- `tests/`：核心测试。

## 后续建议

1. 把 session token 换成 JWT + refresh token；
2. 增加邮箱验证码（注册激活/找回密码）；
3. 对接真实 LLM Provider（按实际 token 消耗结算）；
4. 增加钱包、账本、提现和争议仲裁。
