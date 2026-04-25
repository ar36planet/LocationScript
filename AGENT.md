# ifly — Agent Reference

`ifly` is a macOS CLI tool that simulates GPS location on a connected iPhone via `pymobiledevice3`.
This document is intended for AI agents (Claude, GPT, etc.) that drive ifly through shell commands.

## Integration Options

| Method | Setup | Best for |
|--------|-------|---------|
| **MCP Server** | `ifly agent-setup <tool>` | Gemini CLI, Claude Code, Codex — structured tool calls, no shell needed |
| **CLI + this doc** | No setup | Any agent with shell access |

### MCP Setup (recommended)

Run once after `ifly install`:

```bash
ifly agent-setup gemini    # Gemini CLI  → writes to ~/.gemini/settings.json
ifly agent-setup claude    # Claude Code → runs: claude mcp add ifly -- ifly mcp
ifly agent-setup codex     # Codex       → runs: codex mcp add ifly -- ifly mcp
```

After setup, the agent automatically discovers 16 tools (`ifly_set_location`, `ifly_move_start`, etc.) on startup. **Tunnel is started automatically** when calling `ifly_set_location`, `ifly_clear_location`, or `ifly_move_start` — no manual tunnel management needed.

---

## Quick Start (typical session)

```bash
ifly tunnel start --wait   # start background tunnel, wait for device
ifly location set --lat 25.033 --lng 121.565
ifly location clear
ifly tunnel stop
```

---

## Output Modes

All commands support two output modes:

| Mode | Trigger | Use case |
|------|---------|----------|
| Human-readable | (default) | Interactive use |
| JSON | `--json` flag | Agent / script parsing |

**Always use `--json` when parsing output.** Every `--json` response follows this envelope:

```json
{
  "ok": true,
  "code": "SOME_CODE",
  "message": "Human-readable summary",
  "data": { ... }
}
```

- `ok` — `true` on success, `false` on failure
- `code` — machine-readable status (see each command below)
- `data` — command-specific payload (may be `{}`)

### Exit Codes

| Exit code | Meaning |
|-----------|---------|
| `0` | Success |
| `1` | General error |
| `2` | `PARAM_ERROR` — bad arguments |
| `3` | `ENV_ERROR` — environment problem (no device, tunnel not running, etc.) |
| `4` | `EXEC_ERROR` — subprocess or I/O failure |

---

## Prerequisites

1. iPhone connected via USB (trust prompt accepted)
2. iOS 17+: Developer Mode enabled on device
3. `ifly install` completed (first-time setup)
4. Tunnel running (`ifly tunnel start`)

**Check everything is ready:**

```bash
ifly --json doctor
```

---

## Commands Reference

### `ifly install`

One-time setup. Installs binary to `/usr/local/bin/ifly`, creates tunneld wrappers, configures passwordless sudo.
Run once after downloading the binary. Requires `sudo` (will prompt for password).

```bash
./ifly install
```

This command prints step-by-step progress to stdout and exits with code 0 on success.

---

### `ifly doctor`

Checks environment health.

```bash
ifly --json doctor
```

**Success response (`ok: true`):**
```json
{
  "ok": true,
  "code": "OK",
  "message": "All checks passed",
  "data": {
    "pymobiledevice3_exists": true,
    "version_ok": true,
    "version_output": "pymobiledevice3, version 4.x.x",
    "tunnel_running": true,
    "wrapper_exists": true,
    "sudo_nopasswd_ok": true,
    "sudo_check_output": "usage: ...",
    "device_connected": true,
    "connected_devices": ["00008110-xxxxxxxxxxxx"],
    "default_udid_set": false,
    "default_udid": null,
    "default_udid_online": false
  }
}
```

**Failure response (`ok: false`, code `ENV_ERROR`):**
Same structure, but some fields are `false`. Common failure patterns:

| Field `false` | Action required |
|---------------|-----------------|
| `pymobiledevice3_exists` | Run `ifly install` |
| `wrapper_exists` | Run `ifly install` |
| `sudo_nopasswd_ok` | Run `ifly install` (reconfigures sudoers) |
| `tunnel_running` | Run `ifly tunnel start` |
| `device_connected` | Connect iPhone via USB |
| `default_udid_online` | Run `ifly device select <UDID> --default` |

---

### `ifly device list`

Lists connected iOS devices.

```bash
ifly --json device list
```

**Response:**
```json
{
  "ok": true,
  "code": "OK",
  "message": "2 device(s) found",
  "data": {
    "devices": [
      {
        "udid": "00008110-xxxxxxxxxxxx",
        "name": "iPhone 17",
        "model": "iPhone17,1",
        "ios": "18.4",
        "connection": "USB",
        "default": true
      },
      {
        "udid": "00008120-yyyyyyyyyyyy",
        "name": "iPhone 13 Pro",
        "model": "iPhone14,2",
        "ios": "17.6",
        "connection": "USB",
        "default": false
      }
    ],
    "default_udid": "00008110-xxxxxxxxxxxx"
  }
}
```

- `connection` — `"USB"` or `"Network"` (WiFi); same device on both is deduplicated (USB preferred)
- `default` — which device ifly will use when multiple are connected

---

### `ifly device select <UDID> --default`

Sets the default device (required when multiple devices are connected).

```bash
ifly --json device select 00008110-xxxxxxxxxxxx --default
```

**Response:**
```json
{
  "ok": true,
  "code": "OK",
  "message": "Default device set: 00008110-xxxxxxxxxxxx",
  "data": { "udid": "00008110-xxxxxxxxxxxx", "default": true }
}
```

---

### `ifly tunnel start`

Starts the background tunnel process (required for iOS 17+).

```bash
ifly --json tunnel start
ifly --json tunnel start --wait          # block until device is reachable
ifly --json tunnel start --wait --timeout 30   # custom timeout (default: 15s)
ifly --json tunnel start --interactive   # prompt for sudo password (fallback)
```

**Success response:**
```json
{
  "ok": true,
  "code": "TUNNEL_STARTED",
  "message": "Tunnel started (headless)",
  "data": { "pid": 12345 }
}
```

With `--wait`:
```json
{
  "ok": true,
  "code": "TUNNEL_STARTED",
  "message": "Tunnel started (headless) (device ready)",
  "data": { "pid": 12345 }
}
```

**Failure — sudo not configured:**
```json
{
  "ok": false,
  "code": "ENV_ERROR",
  "message": "sudo NOPASSWD not configured",
  "data": { "sudo_nopasswd_ok": false }
}
```
→ Run `ifly install` to fix, or use `--interactive` to enter password manually.

---

### `ifly tunnel stop`

Stops the tunnel.

```bash
ifly --json tunnel stop
```

**Response:**
```json
{
  "ok": true,
  "code": "TUNNEL_STOPPED",
  "message": "Tunnel stopped",
  "data": {}
}
```

---

### `ifly tunnel restart`

Stops then starts the tunnel. Use after switching devices.

```bash
ifly --json tunnel restart
ifly --json tunnel restart --wait
```

Same response format as `tunnel start`.

---

### `ifly tunnel status`

Checks if the tunnel is running.

```bash
ifly --json tunnel status
```

**Running:**
```json
{
  "ok": true,
  "code": "TUNNEL_RUNNING",
  "message": "Tunnel is running (pid 12345)",
  "data": { "running": true, "pid": 12345 }
}
```

**Not running:**
```json
{
  "ok": true,
  "code": "TUNNEL_STOPPED",
  "message": "Tunnel is not running",
  "data": { "running": false, "pid": null }
}
```

---

### `ifly location set`

Sets the simulated GPS location. Keeps the location alive in the background.

```bash
# By coordinates
ifly --json location set --lat 25.033 --lng 121.565

# By saved favorite name
ifly --json location set --name "台北101"
```

**Success:**
```json
{
  "ok": true,
  "code": "LOCATION_SET",
  "message": "Location set: 25.033, 121.565",
  "data": {
    "pid": 12345,
    "addr": "台北101, 信義路五段7號, 信義區, 台北市, 110, 台灣"
  }
}
```

- `addr` — reverse-geocoded address (from Nominatim, may be absent if request fails)
- `pid` — background keepalive process PID

**Tunnel not running:**
```json
{
  "ok": false,
  "code": "EXEC_ERROR",
  "message": "Failed to set location (exit 1)"
}
```
→ Run `ifly tunnel start` first.

---

### `ifly location status`

Shows the current simulated location.

```bash
ifly --json location status
```

**Active location:**
```json
{
  "ok": true,
  "code": "LOCATION_ACTIVE",
  "message": "Location: 25.033, 121.565",
  "data": {
    "active": true,
    "lat": "25.033",
    "lng": "121.565",
    "pid": 12345
  }
}
```

**Stale (keepalive process died):**
```json
{
  "ok": true,
  "code": "LOCATION_STALE",
  "message": "Location: 25.033, 121.565",
  "data": { "active": false, "lat": "25.033", "lng": "121.565", "pid": null }
}
```

**No location set:**
```json
{
  "ok": true,
  "code": "LOCATION_IDLE",
  "message": "No virtual location set",
  "data": { "active": false }
}
```

---

### `ifly location clear`

Clears the simulated location and restores real GPS.

```bash
ifly --json location clear
```

**Response:**
```json
{
  "ok": true,
  "code": "LOCATION_CLEARED",
  "message": "Location cleared",
  "data": {}
}
```

> After clearing, the Maps app on iPhone may need to be restarted to show real location.

---

### `ifly location parse`

Parses a Google Maps URL or coordinate string, then sets the location.

```bash
# Coordinate string
ifly --json location parse --coords "25.033,121.565"

# Google Maps URL
ifly --json location parse --google-url "https://maps.google.com/..."
```

**Success:** same as `location set` response (code `LOCATION_SET`).

**Parse failure:**
```json
{
  "ok": false,
  "code": "PARAM_ERROR",
  "message": "Cannot parse URL"
}
```

---

### `ifly location move start`

Moves from the current location toward a destination over time (linear interpolation, updates every 5s).

**Requires a current location** (`location set` or `location status` must be active first).

```bash
ifly --json location move start --direction N --distance 1.5 --speed 5
ifly --json location move start --direction 45 --distance 2 --speed 10
```

- `--direction` — compass (`N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`) or degrees `0`–`360`
- `--distance` — distance in km
- `--speed` — speed in km/h

**Response:**
```json
{
  "ok": true,
  "code": "MOVE_STARTED",
  "message": "Moving 1.50 km, ETA 1080s",
  "data": {
    "pid": 12346,
    "eta_seconds": 1080,
    "destination": { "lat": 25.04661, "lng": 121.565 }
  }
}
```

---

### `ifly location move status`

Shows movement progress.

```bash
ifly --json location move status
```

**Moving:**
```json
{
  "ok": true,
  "code": "MOVE_RUNNING",
  "message": "Moving, ~900s remaining",
  "data": {
    "running": true,
    "pid": 12346,
    "progress": 0.17,
    "eta_remaining_seconds": 900,
    "destination": { "lat": 25.04661, "lng": 121.565 }
  }
}
```

**Done or not started:**
```json
{
  "ok": true,
  "code": "MOVE_IDLE",
  "message": "No move in progress",
  "data": { "running": false }
}
```

---

### `ifly location move stop`

Stops ongoing movement. Location stays at the current interpolated position.

```bash
ifly --json location move stop
```

```json
{
  "ok": true,
  "code": "MOVE_STOPPED",
  "message": "Movement stopped",
  "data": {}
}
```

---

### `ifly favorites list`

Lists all saved favorite locations.

```bash
ifly --json favorites list
```

```json
{
  "ok": true,
  "code": "OK",
  "message": "3 favorite(s)",
  "data": {
    "favorites": {
      "台北101": { "lat": "25.033", "lng": "121.565" },
      "台北車站": { "lat": "25.047924", "lng": "121.517081" }
    }
  }
}
```

---

### `ifly favorites add`

Adds a favorite location.

```bash
ifly --json favorites add --name "台北101" --lat 25.033 --lng 121.565
```

```json
{
  "ok": true,
  "code": "OK",
  "message": "Favorite added: 台北101",
  "data": {}
}
```

---

### `ifly favorites delete`

Deletes a favorite.

```bash
ifly --json favorites delete --name "台北101"
```

```json
{
  "ok": true,
  "code": "OK",
  "message": "Favorite deleted: 台北101",
  "data": {}
}
```

---

### `ifly favorites import`

Imports favorites from a JSON file.

Supported file formats:

```json
// Object format
{ "台北101": { "lat": "25.033", "lng": "121.565" } }

// Array format
[{ "name": "台北101", "lat": "25.033", "lng": "121.565", "dwell": 60 }]
```

```bash
ifly --json favorites import --file /path/to/locations.json
```

---

## Common Error Codes and Recovery

| `code` | Meaning | Recovery |
|--------|---------|----------|
| `ENV_ERROR` + no device | iPhone not connected | Connect USB, unlock phone |
| `ENV_ERROR` + multiple devices | Multiple iPhones connected, no default set | `ifly device select <UDID> --default` |
| `ENV_ERROR` + tunnel not running | Tunnel stopped | `ifly tunnel start` |
| `ENV_ERROR` + sudo_nopasswd_ok false | Sudoers not configured | `ifly install` |
| `EXEC_ERROR` + exit 1 | Tunnel not running or device unreachable | `ifly tunnel start --wait` |
| `PARAM_ERROR` | Bad arguments | Check flag names and value ranges |

---

## Recommended Agent Workflow

```bash
# 1. Verify environment
ifly --json doctor

# 2. Start tunnel (if not running)
ifly --json tunnel start --wait

# 3. Set location
ifly --json location set --lat 25.033 --lng 121.565

# 4. (optional) Verify
ifly --json location status

# 5. Clear when done
ifly --json location clear

# 6. Stop tunnel
ifly --json tunnel stop
```

**Multi-device setup (run once):**
```bash
ifly --json device list                               # find UDID
ifly --json device select <UDID> --default            # set default
ifly --json tunnel restart                            # apply change
```
