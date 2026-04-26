# 智能出行 MCP Skill ✈️

智能出行 MCP 技能，支持机票、火车票、酒店实时查询，航班动态追踪，订单管理，景点评价，天气查询等功能。

适配 **OpenClaw**、**Hermes** 等主流智能体平台。

---

## 功能

| 工具 | 说明 |
|------|------|
| `check_flight` | 机票查询（支持时段、航司、价格筛选） |
| `check_train` | 火车票查询（支持车型、座位、时段筛选） |
| `check_hotel` | 酒店查询（支持星级、区域、价格筛选） |
| `check_flight_info` | 航班实时动态（延误/起降状态） |
| `check_pending_order` | 待出行订单查询 |
| `check_history_order` | 历史订单查询 |
| `check_online_reviews` | 酒店/景点评价查询 |
| `rag_retrieve` | 产品政策/退改票规则检索 |
| `search_web` | 联网搜索（餐饮/景点实时信息） |
| `image_online_search` | 景点/目的地图片搜索 |
| `check_select` | 用户选项提取 |
| `check_weather` | 出行目的地天气查询 |

---

## 快速开始

### 1. 克隆技能

```bash
git clone https://github.com/lonngxiang/travel-skill.git
cd travel-skill
```

### 2. 配置服务地址（二选一）

**方式 A：环境变量（推荐）**

```bash
export TRAVEL_MCP_URL=http://<your-mcp-server-host>:<port>/mcp
```

**方式 B：配置文件**

```bash
cp config.example.json config.json
# 编辑 config.json，填写 baseUrl
```

### 3. 调用工具

```bash
# 查酒店
python3 scripts/travel.py tools/call '{"name": "check_hotel", "arguments": {"cityname": "上海", "datein": "2026-05-01"}}'

# 查机票
python3 scripts/travel.py tools/call '{"name": "check_flight", "arguments": {"ori_cityname": "北京", "des_cityname": "上海", "date": "2026-05-01"}}'

# 查高铁
python3 scripts/travel.py tools/call '{"name": "check_train", "arguments": {"ori_cityname": "北京", "des_cityname": "上海", "date": "2026-05-01", "trainType": "G"}}'
```

---

## 智能体接入

### OpenClaw

将本技能目录放入 OpenClaw SKILLs 目录，技能会自动被发现并加载（通过 `SKILL.md` 中的 `openclaw` 元数据）。

设置环境变量或在 OpenClaw 技能配置中填写 `TRAVEL_MCP_URL`。

### Hermes

在 Hermes 智能体配置中引用本技能路径，技能通过 `SKILL.md` 中的 `hermes` 元数据自动适配（`skill_type: mcp`，`transport: streamable-http`）。

---

## 本地 MCP 服务

本技能支持对接本地自建的 MCP Server。Server 端基于 [FastMCP](https://github.com/jlowin/fastmcp) 实现，用 `@mcp.tool()` 装饰器注册工具，通过 `streamable-http` 传输协议对外暴露，无需额外配置即可被本技能的客户端（`scripts/travel.py`）调用。

启动后将 `TRAVEL_MCP_URL` 指向本地地址即可：

```bash
python3 api_fastmcp_server.py
export TRAVEL_MCP_URL=http://127.0.0.1:7020/mcp
```

> Server 代码及数据文件不含在本仓库中。

---

## 目录结构

```
travel-skill/
├── SKILL.md              # 技能文档（含 openclaw/hermes 元数据）
├── config.example.json   # 配置模板（复制为 config.json 并填写 baseUrl）
├── .env.example          # 环境变量模板
├── scripts/
│   └── travel.py  # MCP 客户端主入口
└── references/
    └── api_references.md # 工具详细调用参考
```

---

## 注意事项

- `config.json` 含服务地址，已加入 `.gitignore`，请勿提交到版本库
- 推荐使用环境变量 `TRAVEL_MCP_URL` 管理服务地址
- 无需 Token，无鉴权配置

---

## 许可

MIT License
