# Design Decisions

## Keepalive 在 CLI vs MCP 的行為差異

### 決策
CLI 的 `--keepalive` 僅供人工互動使用；Agent 透過 MCP 呼叫時，keepalive 由 MCP server process 自身維護。

### 背景
CLI `location set --keepalive` 在終端執行時會 block 主 process，等待 Ctrl+C 才停止。
若 agent 透過 subprocess 呼叫 CLI，process 會永久 block，agent 永遠等不到回應。

雖然可用 `sys.stdin.isatty()` 偵測非 TTY 環境並立即回傳，但 keepalive timer 跑在 subprocess 裡——
agent 一旦收到回傳值並結束 subprocess，keepalive 隨之消失，行為不可靠。

### 結論
- **CLI**：`--keepalive` block 前景，Ctrl+C 停止，適合人工操作。
- **MCP server**：server process 長期存活，keepalive 狀態直接維護在 server 記憶體中，
  提供 `set_location`（含 keepalive 選項）與 `stop_keepalive` 兩個 tool，agent 呼叫後立即回傳。
