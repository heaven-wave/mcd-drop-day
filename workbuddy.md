# workbuddy.md

> 本文件用于核验是否符麦当劳程序员创意开发大赛 × WorkBuddy 联动活动奖励条件。
> 内容为本项目在 **WorkBuddy (Agent 模式)** 中的实际开发对话上下文记录。

---

## 一、项目基本信息

| 项目 | 内容 |
|---|---|
| 项目名称 | 麦麦上新日 · MCD Drop Day |
| 仓库名称 | `mcd-drop-day` |
| 开发工具 | **WorkBuddy**（Agent 模式，工作目录 `E:/WorkBuddy工作空间/automation-2026-10-05-18-29-29`） |
| 开发日期 | 2026-10-09 |
| 目标赛事 | 麦当劳程序员创意开发大赛（M-China/mcd-developer-innovation-challenge） |
| 底层能力 | 麦当劳中国官方 MCP（`https://mcp.mcd.cn`） |

---

## 二、WorkBuddy 开发过程记录

### 阶段 1：活动情报收集与规则解读

在 WorkBuddy 中通过联网检索定位到官方活动仓库 `M-China/mcd-developer-innovation-challenge`，
并读取了 `README.md`、`activityGuidelines.md`、`RANKING.md`、`CONTEST_DECLARATION.md` 四个关键文件。

提取出的硬性要求（用于自检）：

- 仓库必须包含：`README.md`、`CONTEST_DECLARATION.md`（内容不可改动）、`MCP_INTEGRATION.md`、源代码
- 参加 WorkBuddy 专项奖励必须提交 `workbuddy.md`
- 项目需为 Public 仓库，创建时间落在 2025-12-25 至 2026-10-25 区间
- 报名 Issue 正文 ≤ 1000 字且不可含图片

同时从 `M-China/mcd-mcp-server` 抓取了 33 个官方工具的准确名称与功能说明，作为开发依据。

### 阶段 2：赛道差异化分析（WorkBuddy 辅助）

WorkBuddy 抓取并分析了活动 `RANKING.md` 实时榜单（更新至 2026-10-09 22:00，共 64 个入榜项目），
识别出四类**已高度拥挤**的题材：

- 省钱 / 精算类（`mcd-saver-strategist`、`mcd-save-master`、`mc-breakeven` 等十余个）
- 营养 / 热量预算类（`mcd-calorie-budget-skill`、`macrobuddy`、`mcd-macro-strategist` 等十余个）
- 积分 / 抽奖量化类（`mcd-points-actuary`、`mcd-lottery-quant`、`mcd-points-vault` 等）
- 通用点餐助手类（`mcd-easy-order`、`mcd-ai-order`、`mcd-order-buddy` 等）

同时注意到 **`mall-*` 商城系列**与 **`query-party-*` 主题活动系列**
这两组工具业内使用率极低 —— 这两组恰好对应「限量周边」与「派对预约」两个真实痛点。

**决策**：避开上述四类红海，切入「限量周边上新 + 到期资产清算 + 主题活动预约」这条几乎无人覆盖的链路。

### 阶段 3：项目脚手架搭建（WorkBuddy 生成）

由 WorkBuddy 直接生成了完整项目结构并写入磁盘，包括：

- `SKILL.md` —— 技能主体，含意图路由表、五级执行链路、优先级打分公式、安全红线
- `references/tools.md` —— 33 个官方工具的分类清单与调用要点
- `scripts/mcd_cli.py` —— MCP Streamable HTTP 客户端 + 上新雷达
- `README.md` / `MCP_INTEGRATION.md` / `CONTEST_DECLARATION.md`
- `LICENSE` / `.gitignore` / `requirements.txt`

### 阶段 4：编码与真机验证（WorkBuddy 执行）

WorkBuddy 在隔离 Python 环境（3.13.12 + venv）中完成：

1. 语法检查 —— `py_compile` 通过
2. 依赖安装 —— `requests` 装入隔离 venv
3. **真机连通性验证** —— 向 `https://mcp.mcd.cn` 实际发起 `initialize` 握手

验证结果：

| 场景 | 结果 |
|---|---|
| 未提供 Token | 正确拦截并提示，退出码 1 |
| 提供无效 Token | 服务端返回 `401`，客户端正确映射为「Token 无效/过期」提示，退出码 1 |
| `scan --help` | 正常输出，参数解析无误 |

> 无效 Token 能拿到服务端 `401` 而非网络错误，证明协议握手、`Authorization` 请求头构造
> 与响应体处理链路均已正确打通。完整数据拉取需在配置真实 Token 后执行。

---

## 三、WorkBuddy 在项目中的具体贡献

| 环节 | WorkBuddy 做了什么 |
|---|---|
| 赛事调研 | 联网定位官方仓库，读取并结构化全部规则文件 |
| 竞争分析 | 抓取实时榜单，统计 64 个项目的题材分布，给出差异化结论 |
| 技术调研 | 抓取 MCP 官方文档，提取 33 个工具的准确签名 |
| 代码生成 | 编写完整 MCP 客户端（含 JSON / SSE 双响应体解析、Session 复用） |
| 质量保障 | 语法检查、隔离环境依赖安装、三种失败路径的真机验证 |
| 合规自检 | 确认 `CONTEST_DECLARATION.md` 逐字未改、仓库内无 Token 明文 |

---

## 四、 MCP 连接器配置方式

在 WorkBuddy 侧边栏【专家·技能·连接器】→【连接器】→【自定义连接器】→【配置 MCP】中填入：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

启用后即可在对话中直接调用麦当劳官方工具。

---

## 五、声明

本项目推荐使用 WorkBuddy 完成创意构思、开发与调试，符合活动联动奖励的参与条件。
本项目为参赛作品，由参赛者独立开发，非麦当劳官方产品。
