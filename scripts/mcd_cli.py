#!/usr/bin/env python3
"""麦麦上新日 CLI / MCD Drop Day CLI.

一个极薄的麦当劳中国 MCP 客户端 + 上新雷达。

设计目标：
    * 零魔法依赖，仅 requests；
    * Token 只从环境变量读取，绝不落盘；
    * 同时吃 JSON 与 SSE 两种响应体；
    * 任何工具返回里没有的数据，原样呈现缺失，不做兜底编造。

用法：
    export MCD_MCP_TOKEN=你的Token
    python scripts/mcd_cli.py check          # 连通性与工具数量
    python scripts/mcd_cli.py tools          # 列出全部可用工具
    python scripts/mcd_cli.py scan           # 生成「今日可抢清单」
    python scripts/mcd_cli.py call now-time-info

注意：scan 为只读操作，不调用任何下单类工具。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖，请先执行: pip install requests")

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"
TOKEN_ENV = "MCD_MCP_TOKEN"

# 会产生真实订单或真实支出的工具，scan 永不触碰。
WRITE_TOOLS = frozenset(
    {"create-order", "cancel-order", "mall-create-order", "party-order-create", "draw-lottery"}
)


class McpError(RuntimeError):
    """MCP 交互层面的错误，message 可直接展示给终端用户。"""


def _hint_for_status(code: int) -> str:
    if code == 401:
        return "Token 无效、已过期或未提供，请到 https://open.mcd.cn/mcp 重新获取"
    if code == 429:
        return "触发限流（每 Token 每分钟 600 次），请降低调用频率后重试"
    return f"服务端返回 HTTP {code}"


class McpClient:
    """麦当劳 MCP Streamable HTTP 客户端。

    协议要点（与官方 README 一致）：
        * 单端点 POST https://mcp.mcd.cn
        * 请求头 Authorization: Bearer <token>
        * initialize 响应可能带回 Mcp-Session-Id，后续请求必须原样携带
        * 响应体可能是 application/json，也可能是 text/event-stream
    """

    def __init__(self, token: str, url: str = DEFAULT_URL, timeout: int = 30) -> None:
        if not token:
            raise McpError(f"未检测到 {TOKEN_ENV}，请先 export {TOKEN_ENV}=<你的MCP Token>")
        self._timeout = timeout
        self.url = url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
        )
        self._mcp_session_id: str | None = None
        self._id = 0
        self._initialized = False

    # ---------- 传输层 ----------

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self._mcp_session_id:
            headers["Mcp-Session-Id"] = self._mcp_session_id

        try:
            resp =             self._session.post(
                self.url, json=payload, headers=headers, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise McpError(f"网络请求失败: {exc}") from exc

        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self._mcp_session_id = sid

        if resp.status_code != 200:
            raise McpError(_hint_for_status(resp.status_code))

        return self._parse_body(resp)

    @staticmethod
    def _parse_body(resp: requests.Response) -> dict[str, Any]:
        """解析 JSON-RPC 响应，兼容 SSE 封装。

        通知类消息（如 notifications/initialized）返回 202 且无 body，
        这里统一返回空 dict，交由调用方忽略。
        """
        text = (resp.text or "").strip()
        if not text:
            return {}

        ctype = resp.headers.get("Content-Type", "")

        if "text/event-stream" in ctype or "\ndata:" in text or text.startswith("data:"):
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    raw = line[len("data:") :].strip()
                    if not raw:
                        continue
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        continue
            raise McpError("SSE 响应中未解析出有效数据")

        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise McpError(f"响应不是合法 JSON: {text[:200]}") from exc

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params

        result = self._post(payload)

        if not result:
            return {}
        if "error" in result:
            err = result["error"]
            raise McpError(f"{method} 调用失败: {err.get('message', err)}")
        return result.get("result", {})

    # ---------- 生命周期 ----------

    def initialize(self) -> dict[str, Any]:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcd-drop-day", "version": "1.0.0"},
            },
        )
        self._rpc("notifications/initialized")
        self._initialized = True
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        return self._rpc("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()
        if name in WRITE_TOOLS and not os.getenv("MCD_ALLOW_WRITE"):
            raise McpError(
                f"{name} 会产生真实订单或真实支出，已阻止执行。"
                f"确认无误请设置环境变量 MCD_ALLOW_WRITE=1"
            )
        return self._rpc("tools/call", {"name": name, "arguments": arguments or {}})


# ---------- 工具结果解析 ----------


def unwrap(result: dict[str, Any]) -> Any:
    """把 tools/call 的结果翻成 Python 对象。

    优先取结构化 structuredContent；否则把 content[].text 拼起来再尝试 JSON 反序列化；
    都失败则返回原始字符串。
    """
    if not isinstance(result, dict):
        return result

    if isinstance(result.get("structuredContent"), dict):
        sc = result["structuredContent"]
        return sc.get("result", sc)

    parts: list[str] = []
    for block in result.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    joined = "\n".join(parts).strip()

    if not joined:
        return None
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return joined


def safe_call(client: McpClient, name: str, args: dict[str, Any] | None = None) -> tuple[Any, str | None]:
    """调用工具，失败时返回 (None, 原因)，不抛异常，便于雷达部分降级。"""
    try:
        raw = client.call_tool(name, args)
    except McpError as exc:
        return None, str(exc)
    if isinstance(raw, dict) and raw.get("isError"):
        return None, f"{name} 返回错误"
    return unwrap(raw), None


# ---------- 上新雷达 ----------


def _as_list(data: Any, *keys: str) -> list[dict[str, Any]]:
    """从各种嵌套形态里尽力掏出一个 dict 列表；掏不出就返回空列表。"""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        # 某些工具会把列表藏在 data / result 一层
        for wrapper in ("data", "result"):
            nested = data.get(wrapper)
            if isinstance(nested, (list, dict)):
                found = _as_list(nested, *keys)
                if found:
                    return found
    return []


def _pick(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if isinstance(item.get(name), (str, int, float)) and item.get(name) not in ("", None):
            return item[name]
    return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def build_scan_report(client: McpClient) -> dict[str, Any]:
    """只读扫描，产出「今日可抢清单」。不触碰任何写实工具。"""
    report: dict[str, Any] = {"generated_at": datetime.now().isoformat(timespec="seconds")}
    notes: list[str] = []

    now, why = safe_call(client, "now-time-info")
    report["server_time"] = now if now is not None else f"获取失败: {why}"

    calendar, why = safe_call(client, "campaign-calendar")
    activities = _as_list(calendar, "activities", "list", "campaigns", "data")
    report["activity_count"] = len(activities)
    report["activities"] = [
        {
            "name": _pick(a, "name", "title", "campaignName", "activityName") or "(未返回名称)",
            "status": _pick(a, "status", "state"),
            "date": _pick(a, "date", "startDate", "startTime"),
        }
        for a in activities[:15]
    ]
    if calendar is None:
        notes.append("活动日历未能获取")

    products, why = safe_call(client, "mall-points-products")
    product_list = _as_list(products, "products", "list", "items", "data")
    report["mall_product_count"] = len(product_list)

    account, why = safe_call(client, "query-my-account")
    points: int | None = None
    expiring: int | None = None
    if isinstance(account, dict):
        points = _to_int(_pick(account, "availablePoints", "points", "balance", "usablePoints"))
        expiring = _to_int(_pick(account, "expiringPoints", "willExpirePoints", "expirePoints"))
    elif account is not None:
        points = _to_int(account)

    report["points"] = {
        "available": points,
        "expiring_soon": expiring,
        # 只陈述事实，不给凑单建议
        "note": "可用积分为 None 表示工具未返回该字段",
    }
    if points is None:
        notes.append("积分账户未能读取")

    # 按「差额从小到大」给商城商品排序：先看能否直接兑换，再看缺口
    scored: list[dict[str, Any]] = []
    for item in product_list:
        name = _pick(item, "productName", "name", "title") or "(未返回名称)"
        need = _to_int(_pick(item, "points", "pointPrice", "needPoints", "price"))
        entry = {
            "name": name,
            "points_required": need,
            "gap": (need - points) if (need is not None and points is not None) else None,
            "affordable": bool(need is not None and points is not None and points >= need),
            "ending_in_days": _pick(item, "remainDays", "daysLeft", "validDays"),
            # 工具未返回库存时不下结论
            "stock": _pick(item, "stock", "inventory", "remainStock") or "未提供",
        }
        scored.append(entry)

    scored.sort(
        key=lambda x: (
            not x["affordable"],
            x["gap"] if x["gap"] is not None and x["gap"] > 0 else 10**9,
            x["points_required"] if x["points_required"] is not None else 10**9,
        )
    )
    report["mall_products"] = scored[:20]
    if not product_list:
        notes.append("麦麦商城未返回在售商品")

    coupons, why = safe_call(client, "query-my-coupons")
    coupon_list = _as_list(coupons, "coupons", "list", "items", "data")
    report["coupon_count"] = len(coupon_list)
    report["coupons"] = [
        {
            "name": _pick(c, "couponName", "name", "title") or "(未返回名称)",
            "expire_date": _pick(c, "expireDate", "endDate", "validEndTime") or "未提供",
        }
        for c in coupon_list[:15]
    ]

    lottery, why = safe_call(client, "query-lottery-info")
    report["lottery"] = "有活动" if lottery is not None else "无返回结果或不支持"
    report["lottery_note"] = "抽奖为不确定获益，本工具不计算期望值，也不建议为抽奖而消费"

    report["notes"] = notes
    return report


# ---------- 命令 ----------


def cmd_check(client: McpClient, _args: argparse.Namespace) -> int:
    client.initialize()
    tools = client.list_tools()
    writable = sorted(t["name"] for t in tools if t.get("name") in WRITE_TOOLS)
    print(f"连接成功        : {client.url}")
    print(f"协议版本        : {PROTOCOL_VERSION}")
    print(f"可用工具数量    : {len(tools)}")
    print(f"下单类工具      : {', '.join(writable) if writable else '无'}")
    print("说明            : 下单类工具默认被本工具锁定，需 MCD_ALLOW_WRITE=1 才会执行")
    return 0


def cmd_tools(client: McpClient, _args: argparse.Namespace) -> int:
    tools = client.list_tools()
    print(f"共 {len(tools)} 个工具：\n")
    for tool in sorted(tools, key=lambda t: t.get("name", "")):
        name = tool.get("name", "?")
        desc = (tool.get("description") or "").replace("\n", " ")
        print(f"  {name}")
        print(f"      {desc}")
    return 0


def cmd_scan(client: McpClient, args: argparse.Namespace) -> int:
    report = build_scan_report(client)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=" * 56)
    print("  麦麦上新日 · 今日可抢清单")
    print("=" * 56)
    print(f"\n[服务端时间] {report['server_time']}")

    print("\n[积分账户]")
    p = report["points"]
    print(f"    可用积分   : {p['available'] if p['available'] is not None else '未能读取'}")
    print(f"    即将过期   : {p['expiring_soon'] if p['expiring_soon'] is not None else '未返回'}")

    print(f"\n[麦麦商城] 在售 {report['mall_product_count']} 件")
    if report["mall_products"]:
        print(f"    {'商品名称':<28} {'所需积分':>10} {'你的积分缺口':>14}")
        print("    " + "-" * 54)
        for item in report["mall_products"]:
            gap = item["gap"]
            if item["affordable"]:
                gap_text = "已够，可直接兑换"
            elif gap is None:
                gap_text = "未知"
            else:
                gap_text = f"还差 {gap}"
            need = item["points_required"] if item["points_required"] is not None else "未提供"
            name = str(item["name"])[:26]
            print(f"    {name:<28} {str(need):>10} {gap_text:>14}")
    else:
        print("    本次未返回在售商品")

    print(f"\n[本月活动] {report['activity_count']} 项")
    for act in report["activities"][:8]:
        status = act["status"] or "未提供状态"
        date = act["date"] or "未提供日期"
        print(f"    [{status}] {act['name']} ({date})")

    print(f"\n[我的优惠券] {report['coupon_count']} 张")
    for coupon in report["coupons"][:8]:
        print(f"    {coupon['name']} —— 到期 {coupon['expire_date']}")

    print(f"\n[积分抽奖] {report['lottery']}")
    print(f"    {report['lottery_note']}")

    if report["notes"]:
        print("\n[数据说明]")
        for note in report["notes"]:
            print(f"    - {note}")

    print("\n所有数据均来自麦当劳中国 MCP 实时返回，本工具不做库存与价格预测。")
    return 0


def cmd_call(client: McpClient, args: argparse.Namespace) -> int:
    arguments: dict[str, Any] = {}
    for pair in args.param or []:
        if "=" not in pair:
            raise McpError(f"参数格式应为 key=value，收到: {pair}")
        key, value = pair.split("=", 1)
        try:
            arguments[key] = json.loads(value)
        except json.JSONDecodeError:
            arguments[key] = value

    raw = client.call_tool(args.tool, arguments)
    if isinstance(raw, dict) and raw.get("isError"):
        print("工具返回错误：", file=sys.stderr)
    data = unwrap(raw)
    if isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcd_cli",
        description="麦当劳中国 MCP 客户端与上新雷达（只读安全）",
    )
    parser.add_argument("--url", default=os.getenv("MCD_MCP_URL", DEFAULT_URL))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="检查连通性与工具数量")
    sub.add_parser("tools", help="列出全部可用工具")
    scan_p = sub.add_parser("scan", help="生成今日可抢清单（只读）")
    scan_p.add_argument("--json", action="store_true", help="以 JSON 输出")

    call_p = sub.add_parser("call", help="调用单个工具")
    call_p.add_argument("tool", help="工具名，如 campaign-calendar")
    call_p.add_argument("--param", action="append", metavar="KEY=VALUE", help="可重复传参")

    args = parser.parse_args(argv)

    client = McpClient(token=os.getenv(TOKEN_ENV, ""), url=args.url)

    handlers = {
        "check": cmd_check,
        "tools": cmd_tools,
        "scan": cmd_scan,
        "call": cmd_call,
    }
    try:
        return handlers[args.command](client, args)
    except McpError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
