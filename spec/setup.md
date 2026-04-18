# ifly CLI 環境設定

## 安裝流程（一次性）

```
1. clone / 下載專案
2. ./setup.sh        ← 只需跑一次，設定 wrapper 與 sudoers
3. python3 ifly.py doctor  ← 確認環境全綠
4. 正常使用 CLI / 接 MCP server
```

`setup.sh` 是機器層級的一次性設定，之後 CLI、MCP server、agent 呼叫都不需要再跑。

---

## 前置需求

- macOS
- `pymobiledevice3` 已安裝（`pipx install pymobiledevice3` 或 `brew install pymobiledevice3`）
- iPhone 已開啟**開發者模式**（設定 → 隱私權與安全性 → 開發者模式）

---

## 1. 建立 Wrapper

為了讓 CLI 以無密碼 sudo 啟停 tunnel，需要將 pymobiledevice3 複製到固定路徑，
並建立一個 stop script，才能在 sudoers 中精確授權。

```bash
# 啟動 wrapper
sudo cp $(which pymobiledevice3) /usr/local/bin/ifly-tunneld
sudo chmod 755 /usr/local/bin/ifly-tunneld

# 停止 wrapper
sudo tee /usr/local/bin/ifly-tunneld-stop > /dev/null << 'EOF'
#!/bin/sh
pkill -9 -f "pymobiledevice3 remote tunneld"
pkill -9 -f "ifly-tunneld remote tunneld"
exit 0
EOF
sudo chmod 755 /usr/local/bin/ifly-tunneld-stop
```

---

## 2. 設定 sudoers

```bash
sudo visudo -f /etc/sudoers.d/ifly
```

加入以下兩行（將 `YOUR_USER` 換成你的帳號，可用 `whoami` 確認）：

```
YOUR_USER ALL=(ALL) NOPASSWD: /usr/local/bin/ifly-tunneld
YOUR_USER ALL=(ALL) NOPASSWD: /usr/local/bin/ifly-tunneld-stop
```

visudo 存檔：按 `i` 編輯 → 貼上 → `Esc` → `:wq` → Enter

---

## 3. 確認設定

```bash
python3 ifly.py doctor
```

所有項目應顯示 `[OK] OK: All checks passed`。

---

## 4. 基本使用流程

```bash
# 啟動 tunnel（背景，無需密碼）
python3 ifly.py tunnel start

# 設定虛擬定位
python3 ifly.py location set --lat 25.033 --lng 121.565

# 清除定位
python3 ifly.py location clear

# 停止 tunnel
python3 ifly.py tunnel stop
```

---

## 注意事項

- iPhone 第一次連線時需插 USB；tunnel 建立後可切換為 WiFi。
- `location set` 會在背景維持一個 DVT session process（PID 記錄於 `~/.local/share/ifly/location.pid`）。
- `location clear` 會同時 kill 該 process 並送出 clear 指令給裝置。
- GUI（app.py）與 CLI 共用同一套 core service，tunnel 狀態互通。
