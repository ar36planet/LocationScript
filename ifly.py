#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys

import config
from core.location_service import clear_location, parse_coords, parse_google_url, set_location
from core.result import Result
from core.storage_service import add_favorite, delete_favorite, import_favorites, list_favorites
from core.tunnel_service import find_pymobiledevice3, start_tunnel, status as tunnel_status, stop_tunnel

DEVICE_DEFAULT_FILE = os.path.join(config.SCRIPT_DIR, "default_device_udid.txt")


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


def _handle_location_set(args) -> Result:
    return set_location(str(args.lat), str(args.lng), fetch_name=False)


def _handle_tunnel_start(args) -> Result:
    return start_tunnel(headless=not args.interactive)


def _handle_location_parse(args) -> Result:
    if args.google_url:
        parsed = parse_google_url(args.google_url)
        if not parsed:
            return Result(False, "PARAM_ERROR", "Cannot parse URL")
        lat, lng, label = parsed
        return Result(True, "OK", "Parsed successfully", data={"lat": lat, "lng": lng, "label": label})

    if args.coords:
        parsed = parse_coords(args.coords)
        if not parsed:
            return Result(False, "PARAM_ERROR", "Invalid coords format")
        lat, lng = parsed
        return Result(True, "OK", "Parsed successfully", data={"lat": lat, "lng": lng})

    return Result(False, "PARAM_ERROR", "Provide --google-url or --coords")


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
        checks["sudo_check_output"] = (sudo_check.stdout or sudo_check.stderr or "").strip()
    except Exception as e:
        checks["sudo_nopasswd_ok"] = False
        checks["sudo_check_output"] = str(e)

    if checks.get("version_ok") and checks.get("sudo_nopasswd_ok"):
        return Result(True, "OK", "All checks passed", data=checks)
    return Result(False, "ENV_ERROR", "Some checks failed", data=checks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ifly",
        description="iOS virtual location tool — CLI interface for ifly.",
    )
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
    tunnel_start.set_defaults(handler=_handle_tunnel_start)

    tunnel_stop = tunnel_sub.add_parser("stop", help="Stop tunneld")
    tunnel_stop.set_defaults(handler=lambda _a: stop_tunnel())

    tunnel_stat = tunnel_sub.add_parser("status", help="Show tunneld running status")
    tunnel_stat.set_defaults(handler=lambda _a: tunnel_status())

    location = top.add_parser("location", help="Set or clear simulated GPS location")
    location_sub = location.add_subparsers(dest="action", required=True)

    location_set = location_sub.add_parser("set", help="Set GPS coordinates")
    location_set.add_argument("--lat", type=float, required=True, help="Latitude (-90 to 90)")
    location_set.add_argument("--lng", type=float, required=True, help="Longitude (-180 to 180)")
    location_set.set_defaults(handler=_handle_location_set)

    location_clear = location_sub.add_parser("clear", help="Clear simulated location")
    location_clear.set_defaults(handler=lambda _a: clear_location())

    location_parse = location_sub.add_parser("parse", help="Parse a Google Maps URL or coordinate string")
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

    doctor = top.add_parser("doctor", help="Check environment: pymobiledevice3, tunnel, sudo permissions")
    doctor.set_defaults(handler=_handle_doctor)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except Exception as e:
        result = Result(False, "UNEXPECTED_ERROR", f"Unexpected error: {e}")

    if args.as_json:
        print(result.to_json())
    else:
        _print_human(result)

    return _result_exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
