# pymobiledevice3 升級計畫（LocationScript / ifly）

本文件針對 LocationScript（`ifly`）升級 `pymobiledevice3` 的操作流程、注意事項、風險與回復方案做整理。

> 重要背景：`ifly install` 會把當下的 `pymobiledevice3` binary 複製成固定路徑 `/usr/local/bin/ifly-tunneld`，並只在 sudoers 放行這個 wrapper。  
> 因此「升級 `pymobiledevice3`」不等於「tunnel 也在用新版本」，必須額外更新 wrapper。

---

## 升級目標

- 將系統上的 `pymobiledevice3`（通常是 `pipx` 安裝）升級到新版本。
- 讓 tunnel wrapper（`/usr/local/bin/ifly-tunneld`）也同步到同一版本，避免「定位指令用新版本、tunneld 用舊版本」造成非預期行為。
- 透過 `ifly doctor` 做升級前後的 smoke test。

---

## 升級前檢查（必做）

1. 記錄目前版本與環境狀態
   - `ifly --json doctor`
   - `which pymobiledevice3`
   - `pymobiledevice3 version`
   - `if [ -x /usr/local/bin/ifly-tunneld ]; then /usr/local/bin/ifly-tunneld version; fi`

2. 確認設備與權限
   - iPhone 已信任（USB）、Developer Mode 已開啟
   - `sudo -n /usr/local/bin/ifly-tunneld --help` 可成功（代表免密 sudo 正常）

3. 確認目前無正在跑的 tunneld（建議）
   - `ifly --json tunnel status`
   - 如正在跑：`ifly --json tunnel stop`

---

## 升級流程（建議順序）

### 1) 升級 `pymobiledevice3`（pipx）

- `pipx upgrade pymobiledevice3`

> 若你是用 Homebrew 安裝：請改用 `brew upgrade pymobiledevice3`（並確認 `which pymobiledevice3` 指到你要的來源）。

### 2) 同步更新 tunnel wrapper（關鍵步驟）

- `ifly update`

`ifly update` 會做三件事：
- 用目前系統找到的 `pymobiledevice3` 覆蓋更新 `/usr/local/bin/ifly-tunneld`
- 重新寫入 `/usr/local/bin/ifly-tunneld-stop`
- 重新寫入並驗證 `/etc/sudoers.d/ifly`

### 3) 升級後 smoke test

- `ifly --json doctor`
- `pymobiledevice3 version`
- `/usr/local/bin/ifly-tunneld version`
- `ifly --json tunnel start --wait`
- `ifly --json location set --lat 25.033 --lng 121.565`
- `ifly --json location clear`
- `ifly --json tunnel stop`

---

## 注意事項與風險清單

### A. 版本來源不一致（最高風險）

症狀：
- `pymobiledevice3 version` 顯示新版本，但 `/usr/local/bin/ifly-tunneld version` 仍是舊版本。

影響：
- tunnel transport / developer services 走不同版本行為，可能出現 intermittent 連線、服務相容性差異、甚至「doctor 看起來 OK 但實際 set/clear 不穩」。

對策：
- 升級後務必跑 `ifly update`，並用 `.../ifly-tunneld version` 驗證 wrapper 同步。

### B. sudoers / 權限風險

症狀：
- `ifly tunnel start` 失敗，訊息提到 `sudo -n` 或需要密碼。

原因：
- `/etc/sudoers.d/ifly` 遺失、內容錯誤、權限非 0440、或 wrapper 路徑不同。

對策：
- `ifly update` 會重建 sudoers 並用 `visudo -cf` 驗證。

### C. iOS / Developer Mode / 配對狀態變動

症狀：
- `usbmux list` 看不到 device，或 developer/dvt 指令失敗。

對策：
- 升級前後都用 `ifly doctor` 比對差異；必要時重新信任、重新插拔 USB、重開 Developer Mode。

### D. 打包版本（PyInstaller）與系統版本混用

若你使用 `.app`（`dist/iOS虛擬定位.app`）：
- 它可能「內含」某一版 `pymobiledevice3`（由打包當下環境決定）。
- `ifly`（系統 CLI）則可能走 `pipx` / brew 版本。

對策：
- 在要發佈/交付的情境，請固定 build 環境並把 `ifly doctor` 納入 build 驗收。

---

## 回復（Rollback）方案

若升級後不穩定：

1. 回退 `pymobiledevice3`
   - `pipx uninstall pymobiledevice3`
   - `pipx install pymobiledevice3==<舊版>`（例如 `7.4.0`）

2. 同步回退 wrapper
   - `ifly update`

3. 驗證回退版本與功能
   - `ifly --json doctor`
   - `pymobiledevice3 version`
   - `/usr/local/bin/ifly-tunneld version`
   - `ifly --json tunnel start --wait`
   - `ifly --json location set --lat 25.033 --lng 121.565`
   - `ifly --json location clear`
   - `ifly --json tunnel stop`
