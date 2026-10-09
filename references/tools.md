# 麦当劳中国 MCP 工具参考

> 数据来源：官方仓库 [M-China/mcd-mcp-server](https://github.com/M-China/mcd-mcp-server) README
> 快照版本：1.0.9（2026-09-10），共 33 个工具。
> 本文件供 Agent 按需查阅，**运行时请以 `tools/list` 的实时返回为准**。

## 速查索引

| 分组 | 工具 |
|---|---|
| 时间基准 | `now-time-info` |
| 活动与券订阅 | `campaign-calendar`、`available-coupons`、`auto-bind-coupons`、`query-my-coupons`、`query-store-coupons` |
| 积分与抽奖 | `query-my-account`、`query-lottery-info`、`draw-lottery`、`query-my-prizes` |
| 麦麦商城 | `mall-points-products`、`mall-product-detail`、`mall-create-order`、`mall-order-list`、`mall-order-detail` |
| 主题活动四级 | `query-party-city`、`query-party-store`、`query-partystore-date`、`query-partystore-session`、`party-order-create` |
| 门店与菜单 | `query-nearby-stores`、`delivery-query-stores`、`delivery-query-addresses`、`delivery-create-address`、`query-meals`、`query-meal-detail`、`query-meal-assistance` |
| 点餐与订单 | `calculate-price`、`create-order`、`cancel-order`、`query-order`、`order-list` |
| 营养 | `list-nutrition-foods` |

---

## 时间基准

### `now-time-info`
获取当前时间信息。
**务必以此工具返回值作为所有时间判断的基准** —— 不要用本地时钟推断「今天」「本月」「还剩几天」。

---

## 活动与券

### `campaign-calendar`
查询麦当劳中国当月营销活动日历。
返回区分**进行中 / 往期 / 未来**三类，本 Skill 重点提取前两类。

### `available-coupons`
查询当前**可领取**的麦麦省券列表（尚未到用户手中）。

### `auto-bind-coupons`
一键领取麦麦省全部当前可用券。无需指定 `couponId`。
写实工具，会产生账户变更，执行前需用户确认。

### `query-my-coupons`
查询账户下**已領**的优惠券列表。临期券识别的输入源。

### `query-store-coupons`
查询指定门店下可用的优惠券。
注意：券的可用性**因门店而异**，跨平台核对时使用此工具而非 `query-my-coupons`。

---

## 积分与抽奖

### `query-my-account`
查询积分账户信息。返回字段包含**可用积分、累计积分、冻结积分、即将过期积分**。
> `即将过期积分` 是本 Skill 的核心价值信号 —— 它是「到期资产清算」的唯一输入。

### `query-lottery-info`
查询当前积分抽奖活动状态、奖品列表、抽奖消耗规则与用户可用资源。

### `draw-lottery`
执行一次积分抽奖，消耗积分或次数。
**不确定获益。** 本 Skill 不为其计算期望值，不为抽奖而建议消费。

### `query-my-prizes`
查询抽奖获得的全部奖品记录，支持分页，按中奖时间倒序。

---

## 麦麦商城

### `mall-points-products`
查询麦麦商城可兑换/可购买商品列表。
> **注意**：官方说明指出该结果**不包括使用积分兑换的第三方兑换码**。

### `mall-product-detail`
查询单个商城商品详情（图片、所需积分、有效期、说明）。
获取精确积分门槛时使用。

### `mall-create-order`
积分兑换虚拟或实物商品，扣减积分并返回兑换订单号或券码。
**写实工具。**

### `mall-order-list` / `mall-order-detail`
查询商城近一年购买或兑换订单列表与详情。

---

## 主题活动（四级串行链路）

```
query-party-city ──cityId──→ query-party-store ──storeId──→ query-partystore-date ──date──→ query-partystore-session
                                                                                                      │
                                                                                               party-order-create
```

1. **`query-party-city`** —— 主题活动的可参与城市列表
2. **`query-party-store`** —— 指定城市下的可参与门店
3. **`query-partystore-date`** —— 指定门店的可预约日期
4. **`query-partystore-session`** —— 指定门店 + 日期的可预约场次
5. **`party-order-create`** —— 选定场次后下单（写实工具）

**严禁跳级，严禁构造 ID。** 每一级入参必须来自上一级真实返回。

---

## 门店与菜单

### `query-nearby-stores`
查询指定地址附近的麦当劳餐厅。

### `delivery-query-stores`
外送场景下查询收货地址附近**可配送**门店。与 `query-nearby-stores` 的区别在于是否支持配送。

### `delivery-query-addresses` / `delivery-create-address`
用户配送地址列表查询与新增。

### `query-meals`
查询当前门店可售卖餐品列表（分类、餐品编码、标签）。点餐选品入口。

### `query-meal-detail`
按餐品编码查详情，用于查看套餐组成与可替换选项。

### `query-meal-assistance`
**仅企业团餐场景**下查询门店支持的助餐服务。普通场景调用无意义。

---

## 点餐与订单

### `calculate-price`
根据用户选购商品列表（可含优惠券）计算商品金额、配送费、优惠金额及应付总价。
> **下单前的必经关卡。** 金额未向用户展示前不得调 `create-order`。

### `create-order`
创建订单，返回订单详情与支付链接。**写实工具。**

### `cancel-order`
取消订单。用户表达取消意图时使用，执行前复述订单号并确认。

### `query-order` / `order-list`
查询订单详情与近期历史订单（**非商城订单**；商城订单用 `mall-order-list`）。

---

## 营养

### `list-nutrition-foods`
获取餐品营养成分数据（能量、蛋白质、脂肪、碳水化合物、钠、钙等）。

**边界约束**：本 Skill 仅如实返回数据，**不做健康建议、不做减脂配餐方案** —— 那既超出能力边界，也会让作品陷入同质化。

---

## 错误码

| code | 原因 | 处理建议 |
|---|---|---|
| `401` | MCP Token 无效、已过期或未提供 | 检查 `Authorization` 请求头；重新获取 Token |
| `429` | 触发限流（>600 次/分钟） | 降低请求频率，控制调用间隔 |

---

## 通用约束

- 协议：Streamable HTTP，最高支持 MCP `2025-06-18`
- 限流：每 Token 每分钟 600 次请求
- 地区：中国大陆（不含港澳台）
- Token 严禁硬编码，仅通过环境变量读取与传输
