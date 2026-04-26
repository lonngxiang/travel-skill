"""
天翼出行 MCP 工具主入口
支持 FastMCP streamable-http 传输协议（含完整 MCP session 握手）

握手流程：
  1. POST initialize         → 获取 Mcp-Session-Id
  2. POST notifications/initialized（携带 session id）
  3. POST tools/list 或 tools/call（携带 session id）

配置优先级（高→低）：
  1. 环境变量 TIANYI_BASE_URL
  2. 同级 config.json 的 baseUrl 字段
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

MCP_PROTOCOL_VERSION = "2024-11-05"


# ─────────────────────────────────────────────
# 配置加载
# ─────────────────────────────────────────────

def load_config() -> Dict[str, Any]:
    """
    加载配置，优先使用环境变量 TIANYI_BASE_URL，
    其次读取 SKILL 目录下的 config.json。
    """
    base_url = os.environ.get("TIANYI_BASE_URL", "").strip()
    if base_url:
        return {"baseUrl": base_url}

    skill_dir = Path(__file__).parent.parent.absolute()
    config_file = skill_dir / "config.json"
    if not config_file.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {config_file}\n"
            "请复制 config.example.json → config.json 并填写 baseUrl，\n"
            "或设置环境变量 TIANYI_BASE_URL。"
        )
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# 使用说明
# ─────────────────────────────────────────────

def print_usage():
    skill_dir = Path(__file__).parent.parent.absolute()
    print(f"""
使用说明：
    python3 scripts/tianyi_travel.py <method> [params]

参数说明：
    method  - MCP 协议的 method 参数（必填）
    params  - MCP 协议的 params 参数（选填，JSON 格式字符串）
              当 method 为 tools/call 时，params 为必填参数

配置方式（二选一）：
    1. 环境变量：export TIANYI_BASE_URL=http://<host>:<port>/mcp
    2. 配置文件：cp config.example.json config.json  # 然后填写 baseUrl

调用示例（在技能目录下执行）：
    cd {skill_dir}
    python3 scripts/tianyi_travel.py tools/list
    python3 scripts/tianyi_travel.py tools/call '{{"name": "check_hotel", "arguments": {{"cityname": "北京", "datein": "2026-05-01"}}}}'
    python3 scripts/tianyi_travel.py tools/call '{{"name": "check_flight", "arguments": {{"ori_cityname": "北京", "des_cityname": "上海", "date": "2026-05-01"}}}}'
    python3 scripts/tianyi_travel.py tools/call '{{"name": "check_train", "arguments": {{"ori_cityname": "北京", "des_cityname": "上海", "date": "2026-05-01"}}}}'
""")


# ─────────────────────────────────────────────
# HTTP 工具
# ─────────────────────────────────────────────

def _post(
    url: str,
    body: Dict[str, Any],
    session_id: Optional[str] = None,
    timeout: int = 60,
) -> Tuple[Optional[str], str]:
    """
    发送单次 POST 请求。
    返回 (session_id（来自响应头或传入值）, response_body_str)
    """
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            returned_session_id = resp.headers.get("Mcp-Session-Id") or session_id
            raw = resp.read().decode("utf-8")
            return returned_session_id, raw
    except urllib.error.HTTPError as e:
        body_str = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {body_str}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"无法连接到天翼出行 MCP 服务 ({url})。\n"
            f"请确认服务已在远程或本地运行。\n"
            f"错误详情: {e.reason}"
        )


def _parse_response(raw: str, target_id: Optional[int] = None) -> Dict[str, Any]:
    """
    解析响应体：支持直接 JSON 和 SSE（text/event-stream）两种格式。
    target_id：期望匹配的 JSON-RPC id，若 SSE 包含多个 data 行则取匹配的那条。
    """
    raw = raw.strip()
    if not raw:
        return {}

    if raw.startswith("{") or raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    candidates = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
            candidates.append(obj)
        except json.JSONDecodeError:
            continue

    if not candidates:
        raise RuntimeError(f"无法从服务响应中解析 JSON:\n{raw[:600]}")

    if target_id is not None:
        for obj in candidates:
            if obj.get("id") == target_id:
                return obj

    return candidates[-1]


# ─────────────────────────────────────────────
# MCP Session 管理
# ─────────────────────────────────────────────

def mcp_call(base_url: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    完整的 FastMCP streamable-http 会话流程：
      1. initialize       → 拿到 Mcp-Session-Id
      2. notifications/initialized（携带 session id，无需响应）
      3. 实际 method 调用（携带 session id）
    """
    init_body = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "tianyi-travel-skill",
                "version": "1.0.0",
            },
        },
    }
    session_id, init_raw = _post(base_url, init_body, timeout=30)

    notif_body = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    _post(base_url, notif_body, session_id, timeout=10)

    request_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    _, raw = _post(base_url, request_body, session_id, timeout=60)
    return _parse_response(raw, target_id=1)


# ─────────────────────────────────────────────
# 输入验证
# ─────────────────────────────────────────────

def validate_json(params_str: str) -> Dict[str, Any]:
    try:
        params = json.loads(params_str)
        if not isinstance(params, dict):
            raise ValueError("params 必须是 JSON 对象格式")
        return params
    except json.JSONDecodeError as e:
        raise ValueError(f"params 参数不是有效的 JSON 格式: {e}")


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("[错误] 缺少 method 参数\n")
        print_usage()
        sys.exit(1)

    method = sys.argv[1]
    params_str = sys.argv[2] if len(sys.argv) > 2 else ""

    if method == "tools/call" and not params_str:
        print("[错误] method 为 tools/call 时，params 参数为必填\n")
        print_usage()
        sys.exit(1)

    params: Dict[str, Any] = {}
    if params_str:
        try:
            params = validate_json(params_str)
        except ValueError as e:
            print(f"[错误] 参数错误: {e}\n")
            print_usage()
            sys.exit(1)

    try:
        config = load_config()
        base_url = config.get("baseUrl", "")
        if not base_url:
            print("[错误] 配置错误: 未找到 baseUrl（检查 config.json 或 TIANYI_BASE_URL 环境变量）")
            sys.exit(1)

        result = mcp_call(base_url, method, params)

        if method == "tools/call" and "result" in result:
            inner = result["result"]
            if "isError" in inner and inner["isError"]:
                for item in inner.get("content", []):
                    if item.get("type") == "text":
                        print(f"[工具错误] {item.get('text', '')}")
            elif "content" in inner:
                for item in inner["content"]:
                    if item.get("type") == "text":
                        print(item.get("text", ""))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif "error" in result:
            err = result["error"]
            print(f"[错误] {err.get('message', json.dumps(err, ensure_ascii=False))}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except FileNotFoundError as e:
        print(f"[错误] 配置错误: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"[错误] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] 请求失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
