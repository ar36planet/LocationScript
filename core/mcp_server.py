"""
Minimal MCP stdio server for ifly.
Implements JSON-RPC 2.0 over stdin/stdout per MCP protocol spec.
Tools delegate to `ifly --json` subprocesses.
"""
import json
import os
import subprocess
import sys

_PROTOCOL_VERSION = "2024-11-05"
_SERVER_NAME = "ifly"

# Path to the ifly binary/script used for subprocess calls
if getattr(sys, "frozen", False):
    _IFLY_CMD: list[str] = [sys.executable]
else:
    _IFLY_CMD = [
        sys.executable,
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ifly.py")),
    ]

_TOOLS = [
    {
        "name": "ifly_set_location",
        "description": (
            "Set simulated GPS location on connected iPhone. "
            "Provide lat/lng for coordinates, or name for a saved favorite. "
            "Tunnel is started automatically if not already running."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude (-90 to 90)"},
                "lng": {"type": "number", "description": "Longitude (-180 to 180)"},
                "name": {"type": "string", "description": "Saved favorite name (alternative to lat/lng)"},
            },
        },
    },
    {
        "name": "ifly_location_status",
        "description": "Get current simulated GPS location status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_clear_location",
        "description": "Clear simulated GPS location and restore real GPS on iPhone. Tunnel is started automatically if not already running.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_tunnel_start",
        "description": "Start the background tunnel (required for iOS 17+).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "wait": {"type": "boolean", "description": "Block until device tunnel is ready"},
            },
        },
    },
    {
        "name": "ifly_tunnel_stop",
        "description": "Stop the background tunnel.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_tunnel_restart",
        "description": "Restart the tunnel. Use after switching devices.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_tunnel_status",
        "description": "Check whether the tunnel is running.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_device_list",
        "description": "List connected iOS devices with UDID, name, iOS version and connection type.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_device_select",
        "description": "Set the default device. Required when multiple devices are connected.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "udid": {"type": "string", "description": "Device UDID"},
            },
            "required": ["udid"],
        },
    },
    {
        "name": "ifly_favorites_list",
        "description": "List all saved favorite locations.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_favorites_add",
        "description": "Add a new favorite location.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Display name"},
                "lat": {"type": "number", "description": "Latitude"},
                "lng": {"type": "number", "description": "Longitude"},
            },
            "required": ["name", "lat", "lng"],
        },
    },
    {
        "name": "ifly_favorites_delete",
        "description": "Delete a saved favorite location by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the favorite to delete"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ifly_move_start",
        "description": (
            "Move simulated location from the current position toward a destination over time. "
            "Tunnel is started automatically if not running. "
            "Updates location every 5 seconds until destination is reached."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "Compass direction (N/NE/E/SE/S/SW/W/NW) or bearing in degrees (0–360)",
                },
                "distance": {"type": "number", "description": "Distance to travel in km"},
                "speed": {"type": "number", "description": "Speed in km/h"},
            },
            "required": ["direction", "distance", "speed"],
        },
    },
    {
        "name": "ifly_move_status",
        "description": "Check movement progress: whether a move is in progress, remaining time and destination.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_move_stop",
        "description": "Stop ongoing movement. Location stays at the last updated position.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ifly_doctor",
        "description": (
            "Check ifly environment health: pymobiledevice3 installed, "
            "tunnel running, sudo NOPASSWD configured, device connected."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _call_ifly(*args: str) -> dict:
    try:
        proc = subprocess.run(
            [*_IFLY_CMD, "--json", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,  # isolate from MCP server's stdin (Gemini JSON-RPC stream)
            text=True,
            timeout=35,
        )
        stdout = proc.stdout.strip()
        if not stdout:
            stderr = (proc.stderr or "").strip()[:300]
            return {
                "ok": False,
                "code": "EXEC_ERROR",
                "message": f"ifly returned no output (exit {proc.returncode}): {stderr}",
            }
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "code": "EXEC_ERROR", "message": f"JSON parse error, raw: {proc.stdout[:200]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": "TIMEOUT", "message": "ifly command timed out"}
    except Exception as e:
        return {"ok": False, "code": "EXEC_ERROR", "message": str(e)}


def _ensure_tunnel() -> dict | None:
    """Start tunnel if not running. Returns error dict on failure, None on success."""
    status = _call_ifly("tunnel", "status")
    if status.get("data", {}).get("running"):
        return None
    result = _call_ifly("tunnel", "start", "--wait")
    if not result.get("ok"):
        return result
    return None


def _dispatch(name: str, args: dict) -> dict:
    if name == "ifly_set_location":
        err = _ensure_tunnel()
        if err:
            return err
        if args.get("name"):
            return _call_ifly("location", "set", "--name", args["name"])
        if args.get("lat") is not None and args.get("lng") is not None:
            return _call_ifly("location", "set", "--lat", str(args["lat"]), "--lng", str(args["lng"]))
        return {"ok": False, "code": "PARAM_ERROR", "message": "Provide lat/lng or name"}

    if name == "ifly_location_status":
        return _call_ifly("location", "status")

    if name == "ifly_clear_location":
        err = _ensure_tunnel()
        if err:
            return err
        return _call_ifly("location", "clear")

    if name == "ifly_tunnel_start":
        cmd = ["tunnel", "start"]
        if args.get("wait"):
            cmd.append("--wait")
        return _call_ifly(*cmd)

    if name == "ifly_tunnel_stop":
        return _call_ifly("tunnel", "stop")

    if name == "ifly_tunnel_restart":
        return _call_ifly("tunnel", "restart")

    if name == "ifly_tunnel_status":
        return _call_ifly("tunnel", "status")

    if name == "ifly_device_list":
        return _call_ifly("device", "list")

    if name == "ifly_device_select":
        return _call_ifly("device", "select", args["udid"], "--default")

    if name == "ifly_favorites_list":
        return _call_ifly("favorites", "list")

    if name == "ifly_favorites_add":
        return _call_ifly(
            "favorites", "add",
            "--name", args["name"],
            "--lat", str(args["lat"]),
            "--lng", str(args["lng"]),
        )

    if name == "ifly_favorites_delete":
        return _call_ifly("favorites", "delete", "--name", args["name"])

    if name == "ifly_move_start":
        err = _ensure_tunnel()
        if err:
            return err
        return _call_ifly(
            "location", "move", "start",
            "--direction", str(args["direction"]),
            "--distance", str(args["distance"]),
            "--speed", str(args["speed"]),
        )

    if name == "ifly_move_status":
        return _call_ifly("location", "move", "status")

    if name == "ifly_move_stop":
        return _call_ifly("location", "move", "stop")

    if name == "ifly_doctor":
        return _call_ifly("doctor")

    return {"ok": False, "code": "UNKNOWN_TOOL", "message": f"Unknown tool: {name}"}


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _respond(req_id, result: dict) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def run() -> None:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")

        # Notifications (no id) require no response
        if req_id is None:
            continue

        if method == "initialize":
            _respond(req_id, {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": _SERVER_NAME, "version": "1.0.0"},
            })

        elif method == "tools/list":
            _respond(req_id, {"tools": _TOOLS})

        elif method == "tools/call":
            params = req.get("params", {})
            result = _dispatch(params.get("name", ""), params.get("arguments", {}))
            _respond(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            })

        elif method == "ping":
            _respond(req_id, {})

        else:
            _error(req_id, -32601, f"Method not found: {method}")
