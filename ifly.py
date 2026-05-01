#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys

import config
import version
from core.location_service import (
    clear_location, location_status, parse_coords, parse_google_url, set_location,
    move_location_run, move_location_start, move_location_stop, move_location_status,
)
from core.result import Result
from core.storage_service import add_favorite, delete_favorite, import_favorites, list_favorites
from core.tunnel_service import find_pymobiledevice3, start_tunnel, status as tunnel_status, stop_tunnel, wait_for_ready

DEVICE_DEFAULT_FILE = config.DEFAULT_UDID_FILE


def _load_default_udid() -> str:
    if os.path.isfile(DEVICE_DEFAULT_FILE):
        with open(DEVICE_DEFAULT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _save_default_udid(udid: str) -> None:
    os.makedirs(config.SCRIPT_DIR, exist_ok=True)
    with open(DEVICE_DEFAULT_FILE, "w", encoding="utf-8") as f:
        f.write(udid.strip())


def _result_exit_code(result: Result) -> int:
    if result.ok:
        return 0
    if result.code == "PARAM_ERROR":
        return 2
    if result.code == "ENV_ERROR":
        return 3
    if result.code == "EXEC_ERROR":
        return 4
    return 1


_SUDOERS_GUIDE = """
── Configure sudo NOPASSWD for tunneld ─────────────────────────
1. Find the pymobiledevice3 path:
     which pymobiledevice3

2. Create a fixed-path wrapper (required for sudoers):
     sudo cp $(which pymobiledevice3) /usr/local/bin/ifly-tunneld
     sudo chmod 755 /usr/local/bin/ifly-tunneld

3. Edit sudoers (use visudo to avoid syntax errors):
     sudo visudo -f /etc/sudoers.d/ifly

   Add this line (replace YOUR_USER with your username):
     YOUR_USER ALL=(ALL) NOPASSWD: /usr/local/bin/ifly-tunneld

4. Run `ifly doctor` to verify the setup.
────────────────────────────────────────────────────────────────"""


def _print_human(result: Result):
    prefix = "OK" if result.ok else "ERR"
    print(f"[{prefix}] {result.code}: {result.message}")
    if result.data:
        print(json.dumps(result.data, ensure_ascii=False, indent=2))
    if isinstance(result.data.get("sudo_nopasswd_ok"), bool) and not result.data["sudo_nopasswd_ok"]:
        print(_SUDOERS_GUIDE)


def _handle_device_list(_args) -> Result:
    cmd = find_pymobiledevice3()
    if not cmd:
        return Result(False, "ENV_ERROR", "pymobiledevice3 not found")

    try:
        proc = subprocess.run([cmd, "usbmux", "list"], capture_output=True, text=True, timeout=12)
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to list devices: {e}")

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        return Result(False, "EXEC_ERROR", f"Failed to list devices: {stderr[:160]}")

    output = (proc.stdout or "").strip()
    default_udid = _load_default_udid()
    try:
        raw_list = json.loads(output)
        devices = [
            {
                "udid": d.get("Identifier", ""),
                "name": d.get("DeviceName", ""),
                "model": d.get("ProductType", ""),
                "ios": d.get("ProductVersion", ""),
                "connection": d.get("ConnectionType", ""),
                "default": d.get("Identifier", "") == default_udid,
            }
            for d in raw_list if isinstance(d, dict)
        ]
    except (json.JSONDecodeError, TypeError):
        udids = sorted(set(re.findall(r"[0-9A-Fa-f-]{24,}", output)))
        devices = [{"udid": u, "default": u == default_udid} for u in udids]

    return Result(
        True,
        "OK",
        f"{len(devices)} device(s) found",
        data={"devices": devices, "default_udid": default_udid},
    )


def _handle_device_select(args) -> Result:
    udid = args.udid.strip()
    if not udid:
        return Result(False, "PARAM_ERROR", "UDID cannot be empty")
    if args.default:
        try:
            _save_default_udid(udid)
        except Exception as e:
            return Result(False, "EXEC_ERROR", f"Failed to save default device: {e}")
        return Result(True, "OK", f"Default device set: {udid}", data={"udid": udid, "default": True})
    return Result(True, "OK", f"Device selected: {udid}", data={"udid": udid, "default": False})


_COMPASS_BEARINGS = {
    "N": 0.0, "NE": 45.0, "E": 90.0, "SE": 135.0,
    "S": 180.0, "SW": 225.0, "W": 270.0, "NW": 315.0,
}


def _parse_direction(value: str) -> float | None:
    upper = value.strip().upper()
    if upper in _COMPASS_BEARINGS:
        return _COMPASS_BEARINGS[upper]
    try:
        deg = float(value)
        if 0.0 <= deg <= 360.0:
            return deg
    except ValueError:
        pass
    return None


def _handle_location_set(args) -> Result:
    if args.name:
        favs_result = list_favorites()
        if not favs_result.ok:
            return favs_result
        favs = favs_result.data.get("favorites", {})
        if args.name not in favs:
            return Result(False, "PARAM_ERROR", f"Favorite not found: '{args.name}'")
        lat = favs[args.name]["lat"]
        lng = favs[args.name]["lng"]
    else:
        if args.lat is None or args.lng is None:
            return Result(False, "PARAM_ERROR", "Provide --lat/--lng or --name")
        lat, lng = str(args.lat), str(args.lng)
    return set_location(lat, lng, fetch_name=True)


def _handle_tunnel_restart(args) -> Result:
    stop_tunnel()
    result = start_tunnel(headless=not getattr(args, "interactive", False))
    if not result.ok:
        return result
    if getattr(args, "wait", False):
        ready = wait_for_ready(timeout=args.timeout)
        if not ready:
            return Result(False, "EXEC_ERROR", f"Tunnel restarted but no device ready within {args.timeout}s")
        return Result(True, result.code, result.message + " (device ready)", data=result.data)
    return result


def _handle_tunnel_start(args) -> Result:
    result = start_tunnel(headless=not args.interactive)
    if not result.ok:
        return result
    if args.wait:
        ready = wait_for_ready(timeout=args.timeout)
        if not ready:
            return Result(False, "EXEC_ERROR", f"Tunnel started but no device ready within {args.timeout}s")
        return Result(True, result.code, result.message + " (device ready)", data=result.data)
    return result


def _handle_location_parse(args) -> Result:
    if args.google_url:
        parsed = parse_google_url(args.google_url)
        if not parsed:
            return Result(False, "PARAM_ERROR", "Cannot parse URL")
        lat, lng, _ = parsed

    elif args.coords:
        parsed = parse_coords(args.coords)
        if not parsed:
            return Result(False, "PARAM_ERROR", "Invalid coords format")
        lat, lng = parsed

    else:
        return Result(False, "PARAM_ERROR", "Provide --google-url or --coords")

    return set_location(lat, lng, fetch_name=True)


def _handle_location_move_start(args) -> Result:
    bearing = _parse_direction(args.direction)
    if bearing is None:
        return Result(False, "PARAM_ERROR",
                      f"Invalid direction '{args.direction}'. Use N/NE/E/SE/S/SW/W/NW or 0–360")
    if args.distance <= 0:
        return Result(False, "PARAM_ERROR", "Distance must be > 0")
    if args.speed <= 0:
        return Result(False, "PARAM_ERROR", "Speed must be > 0")
    return move_location_start(bearing, args.distance, args.speed)


def _handle_move_worker(args) -> Result:
    return move_location_run(
        args.start_lat, args.start_lng,
        args.end_lat, args.end_lng,
        args.speed, args.distance,
    )


def _handle_install(_args) -> Result:
    import shutil

    USER = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    WRAPPER = "/usr/local/bin/ifly-tunneld"
    STOP_WRAPPER = "/usr/local/bin/ifly-tunneld-stop"
    SUDOERS_FILE = "/etc/sudoers.d/ifly"
    IFLY_LINK = "/usr/local/bin/ifly"

    def _step(label: str):
        print(f"\n{label}", flush=True)

    def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, check=True, **kwargs)

    # ── find pymobiledevice3 ─────────────────────────────────────────────────
    _step("[1/5] Checking pymobiledevice3...")
    cmd_path = None
    if getattr(sys, "frozen", False):
        # onefile: binary is extracted to _MEIPASS at runtime
        meipass = getattr(sys, "_MEIPASS", "")
        for candidate in [
            os.path.join(meipass, "pymobiledevice3"),
            os.path.join(os.path.dirname(sys.executable), "pymobiledevice3"),
        ]:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                cmd_path = candidate
                print(f"      Using bundled binary: {cmd_path}", flush=True)
                break
    if not cmd_path:
        cmd_path = find_pymobiledevice3()
    if not cmd_path:
        return Result(False, "ENV_ERROR",
                      "pymobiledevice3 not found. Install it: pipx install pymobiledevice3")
    print(f"      {cmd_path}", flush=True)

    # ── copy binary to /usr/local/bin/ifly ──────────────────────────────────
    _step("[2/5] Installing ifly to /usr/local/bin/ifly...")
    ifly_src = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
    try:
        _run(["sudo", "cp", ifly_src, IFLY_LINK])
        _run(["sudo", "chmod", "755", IFLY_LINK])
        subprocess.run(["sudo", "xattr", "-d", "com.apple.quarantine", IFLY_LINK],
                       capture_output=True)  # ignore error if attribute not present
        _run(["sudo", "codesign", "--force", "--deep", "--sign", "-", IFLY_LINK])
    except subprocess.CalledProcessError as e:
        return Result(False, "EXEC_ERROR", f"Failed to install ifly binary: {e}")
    print("      Done.", flush=True)

    # ── tunneld wrapper ──────────────────────────────────────────────────────
    _step("[3/5] Creating tunneld start wrapper...")
    try:
        _run(["sudo", "cp", cmd_path, WRAPPER])
        _run(["sudo", "chmod", "755", WRAPPER])
    except subprocess.CalledProcessError as e:
        return Result(False, "EXEC_ERROR", f"Failed to create wrapper: {e}")
    print("      Done.", flush=True)

    # ── tunneld stop wrapper ─────────────────────────────────────────────────
    _step("[4/5] Creating tunneld stop wrapper...")
    stop_script = (
        "#!/bin/sh\n"
        "pkill -9 -f 'pymobiledevice3 remote tunneld' 2>/dev/null || true\n"
        "pkill -9 -f 'ifly-tunneld remote tunneld' 2>/dev/null || true\n"
        "exit 0\n"
    )
    try:
        proc = subprocess.Popen(
            ["sudo", "tee", STOP_WRAPPER],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        _, err = proc.communicate(input=stop_script.encode())
        if proc.returncode != 0:
            return Result(False, "EXEC_ERROR", f"Failed to write stop wrapper: {err.decode().strip()[:120]}")
        _run(["sudo", "chmod", "755", STOP_WRAPPER])
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to create stop wrapper: {e}")
    print("      Done.", flush=True)

    # ── sudoers ──────────────────────────────────────────────────────────────
    _step("[5/5] Configuring passwordless sudo for tunnel...")
    if not USER:
        return Result(False, "ENV_ERROR", "Cannot determine current user ($USER unset)")
    sudoers_content = (
        f"{USER} ALL=(ALL) NOPASSWD: {WRAPPER}\n"
        f"{USER} ALL=(ALL) NOPASSWD: {STOP_WRAPPER}\n"
    )
    try:
        proc = subprocess.Popen(
            ["sudo", "tee", SUDOERS_FILE],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        _, err = proc.communicate(input=sudoers_content.encode())
        if proc.returncode != 0:
            return Result(False, "EXEC_ERROR", f"Failed to write sudoers: {err.decode().strip()[:120]}")
        _run(["sudo", "chmod", "440", SUDOERS_FILE])
        check = subprocess.run(
            ["sudo", "visudo", "-cf", SUDOERS_FILE],
            capture_output=True, text=True,
        )
        if check.returncode != 0:
            subprocess.run(["sudo", "rm", "-f", SUDOERS_FILE])
            return Result(False, "EXEC_ERROR", f"sudoers syntax error: {check.stderr.strip()[:120]}")
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"sudoers setup failed: {e}")
    print("      Done.", flush=True)

    print("\n", flush=True)
    print("Optional: integrate with AI agents")
    print("  ifly agent-setup gemini    # Gemini CLI")
    print("  ifly agent-setup claude    # Claude Code")
    print("  ifly agent-setup codex     # OpenAI Codex\n", flush=True)
    return Result(True, "INSTALL_OK", "Installation complete — run 'ifly doctor' to verify", data={
        "ifly": IFLY_LINK,
        "tunneld_wrapper": WRAPPER,
        "pymobiledevice3": cmd_path,
    })

def _handle_update(args) -> Result:
    USER = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    WRAPPER = "/usr/local/bin/ifly-tunneld"
    STOP_WRAPPER = "/usr/local/bin/ifly-tunneld-stop"
    SUDOERS_FILE = "/etc/sudoers.d/ifly"

    def _step(label: str):
        print(f"\n{label}", flush=True)

    def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, check=True, **kwargs)

    cmd_path = find_pymobiledevice3()
    if not cmd_path:
        return Result(False, "ENV_ERROR", "pymobiledevice3 not found. Install/upgrade it first (pipx/brew).")

    checks: dict = {"pymobiledevice3": cmd_path}
    try:
        ver = subprocess.run([cmd_path, "version"], capture_output=True, text=True, timeout=10)
        checks["pymobiledevice3_version"] = (ver.stdout or ver.stderr or "").strip()
    except Exception as e:
        checks["pymobiledevice3_version"] = str(e)

    if os.path.isfile(WRAPPER) and os.access(WRAPPER, os.X_OK):
        try:
            wv = subprocess.run([WRAPPER, "version"], capture_output=True, text=True, timeout=10)
            checks["wrapper_version_before"] = (wv.stdout or wv.stderr or "").strip()
        except Exception as e:
            checks["wrapper_version_before"] = str(e)
    else:
        checks["wrapper_version_before"] = None

    # ── refresh tunneld wrapper ─────────────────────────────────────────────
    _step("[1/3] Refreshing tunneld wrapper...")
    try:
        _run(["sudo", "cp", cmd_path, WRAPPER])
        _run(["sudo", "chmod", "755", WRAPPER])
    except subprocess.CalledProcessError as e:
        return Result(False, "EXEC_ERROR", f"Failed to refresh {WRAPPER}: {e}", data=checks)
    print("      Done.", flush=True)

    # ── refresh stop wrapper ────────────────────────────────────────────────
    _step("[2/3] Refreshing tunneld stop wrapper...")
    stop_script = (
        "#!/bin/sh\n"
        "pkill -9 -f 'pymobiledevice3 remote tunneld' 2>/dev/null || true\n"
        "pkill -9 -f 'ifly-tunneld remote tunneld' 2>/dev/null || true\n"
        "exit 0\n"
    )
    try:
        proc = subprocess.Popen(
            ["sudo", "tee", STOP_WRAPPER],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        _, err = proc.communicate(input=stop_script.encode())
        if proc.returncode != 0:
            return Result(False, "EXEC_ERROR", f"Failed to write {STOP_WRAPPER}: {err.decode().strip()[:160]}",
                          data=checks)
        _run(["sudo", "chmod", "755", STOP_WRAPPER])
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to refresh {STOP_WRAPPER}: {e}", data=checks)
    print("      Done.", flush=True)

    # ── sudoers ─────────────────────────────────────────────────────────────
    _step("[3/3] Refreshing sudoers (passwordless tunnel)...")
    if args.skip_sudoers:
        print("      Skipped (--skip-sudoers).", flush=True)
    else:
        if not USER:
            return Result(False, "ENV_ERROR", "Cannot determine current user ($USER unset)", data=checks)
        sudoers_content = (
            f"{USER} ALL=(ALL) NOPASSWD: {WRAPPER}\n"
            f"{USER} ALL=(ALL) NOPASSWD: {STOP_WRAPPER}\n"
        )
        try:
            proc = subprocess.Popen(
                ["sudo", "tee", SUDOERS_FILE],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            _, err = proc.communicate(input=sudoers_content.encode())
            if proc.returncode != 0:
                return Result(False, "EXEC_ERROR", f"Failed to write sudoers: {err.decode().strip()[:160]}",
                              data=checks)
            _run(["sudo", "chmod", "440", SUDOERS_FILE])
            check = subprocess.run(
                ["sudo", "visudo", "-cf", SUDOERS_FILE],
                capture_output=True, text=True,
            )
            if check.returncode != 0:
                subprocess.run(["sudo", "rm", "-f", SUDOERS_FILE])
                return Result(False, "EXEC_ERROR", f"sudoers syntax error: {check.stderr.strip()[:160]}",
                              data=checks)
        except Exception as e:
            return Result(False, "EXEC_ERROR", f"sudoers setup failed: {e}", data=checks)
        print("      Done.", flush=True)

    try:
        wv = subprocess.run([WRAPPER, "version"], capture_output=True, text=True, timeout=10)
        checks["wrapper_version_after"] = (wv.stdout or wv.stderr or "").strip()
    except Exception as e:
        checks["wrapper_version_after"] = str(e)

    return Result(True, "UPDATE_OK", "Update complete — run 'ifly doctor' to verify", data=checks)


def _handle_mcp(_args):
    from core.mcp_server import run as mcp_run
    mcp_run()
    return None


def _handle_agent_setup(args) -> Result:
    tool = args.tool
    if tool == "gemini":
        return _setup_gemini()
    if tool == "claude":
        return _setup_claude()
    if tool == "codex":
        return _setup_codex()
    return Result(False, "PARAM_ERROR", f"Unknown tool: {tool}")


def _setup_gemini() -> Result:
    settings_path = os.path.expanduser("~/.gemini/settings.json")
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except FileNotFoundError:
        settings = {}
    except json.JSONDecodeError:
        return Result(False, "EXEC_ERROR", f"Cannot parse {settings_path}")

    settings.setdefault("mcpServers", {})["ifly"] = {"command": "ifly", "args": ["mcp"]}

    try:
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        return Result(False, "EXEC_ERROR", f"Failed to write {settings_path}: {e}")

    return Result(True, "OK", f"ifly MCP server registered in {settings_path}",
                  data={"config_file": settings_path})


def _setup_claude() -> Result:
    try:
        proc = subprocess.run(
            ["claude", "mcp", "add", "ifly", "--", "ifly", "mcp"],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip()[:160]
            return Result(False, "EXEC_ERROR", f"claude mcp add failed: {msg}")
        return Result(True, "OK", "ifly MCP server registered in Claude Code")
    except FileNotFoundError:
        return Result(False, "ENV_ERROR", "claude CLI not found. Install Claude Code first.")
    except Exception as e:
        return Result(False, "EXEC_ERROR", str(e))


def _setup_codex() -> Result:
    try:
        proc = subprocess.run(
            ["codex", "mcp", "add", "ifly", "--", "ifly", "mcp"],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip()[:160]
            return Result(False, "EXEC_ERROR", f"codex mcp add failed: {msg}")
        return Result(True, "OK", "ifly MCP server registered in Codex")
    except FileNotFoundError:
        return Result(False, "ENV_ERROR", "codex CLI not found. Install Codex first.")
    except Exception as e:
        return Result(False, "EXEC_ERROR", str(e))


def _handle_doctor(_args) -> Result:
    checks = {}

    cmd = find_pymobiledevice3()
    checks["pymobiledevice3_exists"] = bool(cmd)
    if not cmd:
        return Result(False, "ENV_ERROR", "pymobiledevice3 not found", data=checks)

    try:
        ver = subprocess.run([cmd, "version"], capture_output=True, text=True, timeout=10)
        checks["version_ok"] = ver.returncode == 0
        checks["version_output"] = (ver.stdout or ver.stderr or "").strip()
    except Exception as e:
        checks["version_ok"] = False
        checks["version_output"] = str(e)

    st = tunnel_status()
    checks["tunnel_running"] = bool(st.data.get("running"))

    wrapper = "/usr/local/bin/ifly-tunneld"
    checks["wrapper_exists"] = os.path.isfile(wrapper) and os.access(wrapper, os.X_OK)
    try:
        sudo_check = subprocess.run(
            ["sudo", "-n", wrapper, "remote", "tunneld", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        checks["sudo_nopasswd_ok"] = sudo_check.returncode == 0
        raw = (sudo_check.stdout or sudo_check.stderr or "").strip()
        checks["sudo_check_output"] = raw.splitlines()[0] if raw else ""
    except Exception as e:
        checks["sudo_nopasswd_ok"] = False
        checks["sudo_check_output"] = str(e)

    from core.location_service import _connected_udids
    connected = _connected_udids()
    checks["device_connected"] = len(connected) > 0
    checks["connected_devices"] = connected

    saved_udid = ""
    try:
        with open(config.DEFAULT_UDID_FILE) as f:
            saved_udid = f.read().strip()
    except FileNotFoundError:
        pass
    checks["default_udid_set"] = bool(saved_udid)
    checks["default_udid"] = saved_udid or None
    checks["default_udid_online"] = saved_udid in connected if saved_udid else False

    all_ok = (checks.get("version_ok") and checks.get("sudo_nopasswd_ok")
              and checks["device_connected"] and (not saved_udid or checks["default_udid_online"]))
    if all_ok:
        return Result(True, "OK", "All checks passed", data=checks)
    return Result(False, "ENV_ERROR", "Some checks failed", data=checks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ifly",
        description="iOS virtual location tool — CLI interface for ifly.",
    )
    parser.add_argument("--version", "-V", action="version", version=f"ifly {version.__version__}")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output machine-readable JSON")

    top = parser.add_subparsers(dest="group", required=True)

    device = top.add_parser("device", help="Manage connected iOS devices")
    device_sub = device.add_subparsers(dest="action", required=True)
    device_list = device_sub.add_parser("list", help="List connected devices")
    device_list.set_defaults(handler=_handle_device_list)

    device_select = device_sub.add_parser("select", help="Select active device")
    device_select.add_argument("udid", help="Device UDID")
    device_select.add_argument("--default", action="store_true", help="Save as default device")
    device_select.set_defaults(handler=_handle_device_select)

    tunnel = top.add_parser("tunnel", help="Manage pymobiledevice3 tunnel (tunneld)")
    tunnel_sub = tunnel.add_subparsers(dest="action", required=True)
    tunnel_start = tunnel_sub.add_parser("start", help="Start tunneld in background (requires NOPASSWD sudo)")
    tunnel_start.add_argument("--interactive", action="store_true", help="Prompt for sudo password instead of using NOPASSWD")
    tunnel_start.add_argument("--wait", action="store_true", help="Wait until a device tunnel is ready before returning")
    tunnel_start.add_argument("--timeout", type=int, default=15, metavar="SEC", help="Timeout for --wait (default: 15s)")
    tunnel_start.set_defaults(handler=_handle_tunnel_start)

    tunnel_stop = tunnel_sub.add_parser("stop", help="Stop tunneld")
    tunnel_stop.set_defaults(handler=lambda _a: stop_tunnel())

    tunnel_restart = tunnel_sub.add_parser("restart", help="Restart tunneld (useful after switching devices)")
    tunnel_restart.add_argument("--wait", action="store_true", help="Wait until a device tunnel is ready before returning")
    tunnel_restart.add_argument("--timeout", type=int, default=15, metavar="SEC")
    tunnel_restart.set_defaults(handler=_handle_tunnel_restart)

    tunnel_stat = tunnel_sub.add_parser("status", help="Show tunneld running status")
    tunnel_stat.set_defaults(handler=lambda _a: tunnel_status())

    location = top.add_parser("location", help="Set or clear simulated GPS location")
    location_sub = location.add_subparsers(dest="action", required=True)

    location_set = location_sub.add_parser("set", help="Set GPS coordinates or go to a saved favorite")
    location_set.add_argument("--lat", type=float, default=None, help="Latitude (-90 to 90)")
    location_set.add_argument("--lng", type=float, default=None, help="Longitude (-180 to 180)")
    location_set.add_argument("--name", default=None, metavar="NAME", help="Favorite location name")
    location_set.set_defaults(handler=_handle_location_set)

    location_stat = location_sub.add_parser("status", help="Show current virtual location")
    location_stat.set_defaults(handler=lambda _a: location_status())

    location_clear = location_sub.add_parser("clear", help="Clear simulated location")
    location_clear.set_defaults(handler=lambda _a: clear_location())

    move = location_sub.add_parser("move", help="Move from current location in a direction")
    move_sub = move.add_subparsers(dest="action", required=True)

    move_start = move_sub.add_parser("start", help="Start background movement")
    move_start.add_argument("--direction", required=True, metavar="DIR",
                            help="Bearing in degrees (0–360) or compass (N/NE/E/SE/S/SW/W/NW)")
    move_start.add_argument("--distance", type=float, required=True, metavar="KM", help="Distance in km")
    move_start.add_argument("--speed", type=float, required=True, metavar="KMH", help="Speed in km/h")
    move_start.set_defaults(handler=_handle_location_move_start)

    move_stop = move_sub.add_parser("stop", help="Stop ongoing movement")
    move_stop.set_defaults(handler=lambda _a: move_location_stop())

    move_status = move_sub.add_parser("status", help="Show movement progress")
    move_status.set_defaults(handler=lambda _a: move_location_status())

    location_parse = location_sub.add_parser("parse", help="Parse a Google Maps URL or coordinate string and set location")
    parse_group = location_parse.add_mutually_exclusive_group(required=True)
    parse_group.add_argument("--google-url", metavar="URL", help="Google Maps URL")
    parse_group.add_argument("--coords", metavar="LAT,LNG", help="Coordinate string, e.g. '25.033,121.565'")
    location_parse.set_defaults(handler=_handle_location_parse)

    favorites = top.add_parser("favorites", help="Manage saved locations")
    favorites_sub = favorites.add_subparsers(dest="action", required=True)

    fav_list = favorites_sub.add_parser("list", help="List all saved favorites")
    fav_list.set_defaults(handler=lambda _a: list_favorites())

    fav_add = favorites_sub.add_parser("add", help="Add a new favorite")
    fav_add.add_argument("--name", required=True, help="Display name")
    fav_add.add_argument("--lat", type=float, required=True, help="Latitude")
    fav_add.add_argument("--lng", type=float, required=True, help="Longitude")
    fav_add.set_defaults(handler=lambda a: add_favorite(a.name, str(a.lat), str(a.lng)))

    fav_delete = favorites_sub.add_parser("delete", help="Delete a favorite by name")
    fav_delete.add_argument("--name", required=True, help="Name of the favorite to delete")
    fav_delete.set_defaults(handler=lambda a: delete_favorite(a.name))

    fav_import = favorites_sub.add_parser("import", help="Import favorites from a JSON file")
    fav_import.add_argument("--file", required=True, metavar="PATH", help="Path to JSON file")
    fav_import.set_defaults(handler=lambda a: import_favorites(a.file))

    # Internal worker subcommand — not shown in help
    worker = top.add_parser("_move_worker")
    worker.add_argument("--start-lat", type=float, required=True)
    worker.add_argument("--start-lng", type=float, required=True)
    worker.add_argument("--end-lat", type=float, required=True)
    worker.add_argument("--end-lng", type=float, required=True)
    worker.add_argument("--speed", type=float, required=True)
    worker.add_argument("--distance", type=float, required=True)
    worker.set_defaults(handler=_handle_move_worker)

    doctor = top.add_parser("doctor", help="Check environment: pymobiledevice3, tunnel, sudo permissions")
    doctor.set_defaults(handler=_handle_doctor)

    install = top.add_parser("install", help="One-time setup: install ifly, configure tunneld and sudoers")
    install.set_defaults(handler=_handle_install)

    update = top.add_parser("update", help="Refresh tunneld wrapper + sudoers after pymobiledevice3 upgrade")
    update.add_argument("--skip-sudoers", action="store_true",
                        help="Update wrappers only; do not touch /etc/sudoers.d/ifly")
    update.set_defaults(handler=_handle_update)

    mcp = top.add_parser("mcp", help="Start MCP stdio server (for AI agent integration)")
    mcp.set_defaults(handler=_handle_mcp)

    agent_setup = top.add_parser("agent-setup", help="Register ifly MCP server with an AI tool")
    agent_setup.add_argument(
        "tool",
        choices=["gemini", "claude", "codex"],
        help="AI tool to configure: gemini | claude | codex",
    )
    agent_setup.set_defaults(handler=_handle_agent_setup)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except Exception as e:
        result = Result(False, "UNEXPECTED_ERROR", f"Unexpected error: {e}")

    if result is None:
        return 0

    if args.as_json:
        print(result.to_json())
    else:
        _print_human(result)

    return _result_exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
