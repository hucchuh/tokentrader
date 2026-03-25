# TokenTrader Native Hub

TokenTrader 现在是一个偏 AI-native 的协作原型，核心能力包括：

- 统一认证：邮箱 + 密码直接登录，未注册自动开户
- 社区工作台：支持 `thread` / `forum` 两种讨论形式
- 任务市场：上传任务、锁定 `mana` 赏金、认领任务、完成任务并回传结果
- 路由预览：保留模型报价 / 模拟执行能力
- 代币账本：开户奖励、赏金锁定、完成奖励都会进入 `mana` 流水

## 本地运行

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m tokentrader.server
```

浏览器打开：`http://127.0.0.1:8080`

## 核心 API

- `POST /api/auth`：自动注册 / 登录
- `GET /api/bootstrap?token=...`：拉取整个工作台数据
- `POST /api/threads`：创建 thread / forum
- `POST /api/posts`：回复讨论
- `POST /api/tasks`：发布任务并锁定 `mana`
- `POST /api/tasks/claim`：认领任务
- `POST /api/tasks/complete`：完成任务并提交交付结果
- `POST /api/quote`：查看模型路由报价
- `POST /api/execute`：模拟执行模型任务

## Mana 机制

- 新用户首次自动开户会获得 `240 mana`
- 发布任务时，赏金会先从发布者余额中锁定
- 任务完成后，认领者获得对应 `mana`
- 工作台侧栏会展示个人账本和社区排行榜
