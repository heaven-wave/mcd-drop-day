# 麦麦上新日 · MCD Drop Day

> 麦当劳最容易被错过的东西，从来不是菜单上的菜。

**一个把「限量周边上新、麦麦商城兑换、到期积分清算、主题活动预约」收进同一条链路的 McDonald's MCP Skill。**

![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-FF6B00) ![Python](https://img.shields.io/badge/Python-3.9+-blue) ![Region](https://img.shields.io/badge/Coverage-中国大陆-lightgrey)

---

## 为什么做这个

麦当劳周边里有三类东西，用户几乎每次都是**事后才知道**：

1. **限量周边上新** —— 联名玩具、猫窝、限定包装，限时限量，知道了也常常错过了。
2. **麦麦商城积分兑换** —— 有积分才能换，但没人提醒你「现在这笔积分刚好够换某某」。
3. **即将清空的资产** —— 快过期的积分、临期的优惠券，很多人是过期后才发现。

现有的问题是：这些东西散落在**不同入口**，用户需要自己一个个翻，还要自己算积分够不够。

本项目把这条链路压成一句话：**今天有什么能抢，我够不够格，够格就帮我拿下。**

而且它是**只读安全**的：默认锁定所有会产生真实订单的工具，只有显式设置 `MCD_ALLOW_WRITE=1` 才会放行。

---

## 三条主链路

### 1. 上新雷达
```
now-time-info → campaign-calendar → mall-points-products
              → query-my-account → query-my-coupons → query-lottery-info
```
产出「今日可抢清单」，按 **时效紧迫度 × 资格匹配度 × 稀缺度** 排序，每组明确标出：够不够换、还差多少、什么时候到期。

### 2. 到期资产清算
读取 `query-my-account` 的**即将过期积分**字段，倒推「这笔积分别在过期前能换成什么」，并列展示确定兑换与抽奖两条路 —— **不做期望值诱导，不为了凑积分建议消费。**

### 3. 主题活动预约
严格走四级依赖链路，不跳级、不构造 ID：
```
query-party-city → query-party-store → query-partystore-date → query-partystore-session → party-order-create
```

---

## 目标用户

| 人群 | 他们的问题 | 本项目怎么解决 |
|---|---|---|
| **麦当劳周边收藏者** | 联名上新永远抢不到 | 一条命令拉当天全部在售限量品，按「够了/还差多少」排好 |
| **有积分但不会用的人** | 积分攒着不知不觉过期 | 主动读取即将过期字段，倒推可换清单 |
| **想办麦当劳生日会的家长** | 不知道哪些店能约、约不上 | 城市 → 门店 → 日期 → 场次，四级链路一路查到可选场次 |
| **MCP / Agent 开发者** | 想看一个完整严肃的 MCP Skill 长什么样 | 框架无关设计 + 可运行客户端 + 显式安全边界 |

---

## 安装

### 前置：获取 MCP Token

1. 打开 https://open.mcd.cn/mcp ，手机号登录
2. 【控制台】→【激活】→ 同意服务协议
3. 复制 Token

### 安装本项目

```bash
git clone https://github.com/<你的用户名>/mcd-drop-day.git
cd mcd-drop-day
pip install -r requirements.txt
```

### 配置 Token

```bash
# Linux / macOS
export MCD_MCP_TOKEN=你的Token

# Windows PowerShell
$env:MCD_MCP_TOKEN="你的Token"
```

> 请勿把 Token 写进任何文件。仓库的 `.gitignore` 已排除 `.env`。

---

## 使用示例

### 连通性自检

```bash
python scripts/mcd_cli.py check
```

```
连接成功        : https://mcp.mcd.cn
协议版本        : 2025-06-18
可用工具数量    : 33
下单类工具      : create-order, cancel-order, mall-create-order, party-order-create, draw-lottery
说明            : 下单类工具默认被本工具锁定，需 MCD_ALLOW_WRITE=1 才会执行
```

### 生成今日可抢清单

```bash
python scripts/mcd_cli.py scan
```

```
========================================================
  麦麦上新日 · 今日可抢清单
========================================================

[积分账户]
    可用积分   : 3120
    即将过期   : 500

[麦麦商城] 在售 12 件
    商品名称                         所需积分    你的积分缺口
    ------------------------------------------------------
    麦麦环保袋                           800   已够，可直接兑换
    麦旋风主题钥匙扣                    1500   已够，可直接兑换
    限量联名马克杯                      3500     还差 380
    麦麦儿童绘本套装                    5200     还差 2080

[本月活动] 6 项
    [进行中] 会员积分翻倍 (2026-10-01)
    [即将开始] 万圣节限定回归 (2026-10-18)

[我的优惠券] 8 张
    薯条免费升大 —— 到期 2026-10-12

[积分抽奖] 有活动
    抽奖为不确定获益，本工具不计算期望值，也不建议为抽奖而消费

所有数据均来自麦当劳中国 MCP 实时返回，本工具不做库存与价格预测。
```

### 其他命令

```bash
python scripts/mcd_cli.py tools                       # 列出全部工具
python scripts/mcd_cli.py scan --json                 # JSON 输出，便于二次处理
python scripts/mcd_cli.py call now-time-info          # 调用任意单个工具
python scripts/mcd_cli.py call campaign-calendar
```

### 作为 Skill 装载（推荐）

本 Skill 不绑定任何特定 Agent 框架 —— `SKILL.md` 全程使用官方工具名描述流程，因此可接入任意支持 MCP 的框架。
把 `SKILL.md` 与 `references/` 放到你的 Agent 的 skills 目录即可。

---

## 项目结构

```
mcd-drop-day/
├── README.md                    项目介绍
├── CONTEST_DECLARATION.md       参赛声明（官方原版，未作改动）
├── MCP_INTEGRATION.md           MCP 接入与调用链路说明
├── workbuddy.md                 WorkBuddy 开发上下文（联动奖励核验用）
├── SKILL.md                     技能主体，Agent 运行时加载
├── references/
│   └── tools.md                 33 个官方工具清单与调用要点
├── scripts/
│   └── mcd_cli.py               MCP Streamable HTTP 客户端 + 上新雷达
└── requirements.txt
```

---

## 安全边界

- Token 仅从环境变量读取，**不落盘、不打印**。
- `create-order` / `cancel-order` / `mall-create-order` / `party-order-create` / `draw-lottery` 五个写实工具**默认禁用**，需显式 `MCD_ALLOW_WRITE=1`。
- 未请求的场外地址一律不走；仅直连 `https://mcp.mcd.cn`。
- 遵守限流：每 Token 每分钟 600 次，遇 429 降频重试一次后停止。

---

## 已知限制

- 麦当劳中国官方 MCP 仅覆盖中国大陆（不含港澳台）。
- 工具未返回的字段（如某些商品的库存），本项目如实呈现「未提供」，**不推测、不补全**。
- 命令行工具不做自动下单；自动下单需在 Agent 模式下经用户确认后执行。

---

## 许可

MIT License。详见 [LICENSE](LICENSE)。

本项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，非麦当劳官方产品。
