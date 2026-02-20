#!/bin/zsh

set_location() {
    echo "設定位置：$1, $2"
    pymobiledevice3 developer dvt simulate-location set -- "$1" "$2"
}

case "$1" in
    set)
        if [[ -z "$2" || -z "$3" ]]; then
            echo "錯誤：請提供緯度和經度"
            echo "範例：loc set 25.0330 121.5654"
            exit 1
        fi
        set_location "$2" "$3"
        ;;
    go)
        case "$2" in
            taipei101)      echo "前往：台北101";    set_location 25.0330 121.5654 ;;
            taipei-station) echo "前往：台北車站";   set_location 25.0478 121.5170 ;;
            xinyi)          echo "前往：信義區";     set_location 25.0360 121.5680 ;;
            tokyo)          echo "前往：東京駅";     set_location 35.6812 139.7671 ;;
            shinjuku)       echo "前往：新宿";       set_location 35.6896 139.7006 ;;
            osaka)          echo "前往：大阪駅";     set_location 34.7024 135.4959 ;;
            keelung-shell)  echo "前往: 基隆貝殼純點"; set_location 25.161110 121.762787;;
            *)
                echo "找不到地點：$2"
                echo "可用地點：taipei101, taipei-station, xinyi, tokyo, shinjuku, osaka"
                exit 1
                ;;
        esac
        ;;
    clear)
        echo "清除模擬位置..."
        pymobiledevice3 developer dvt simulate-location clear
        ;;
    list)
        echo "預設地點："
        echo "  taipei101      - 台北101 (25.0330, 121.5654)"
        echo "  taipei-station - 台北車站 (25.0478, 121.5170)"
        echo "  xinyi          - 信義區 (25.0360, 121.5680)"
        echo "  tokyo          - 東京駅 (35.6812, 139.7671)"
        echo "  shinjuku       - 新宿 (35.6896, 139.7006)"
        echo "  osaka          - 大阪駅 (34.7024, 135.4959)"
        echo "  keelung-shell  - 基隆貝殼純點(25.161110, 121.762787)"
        ;;
    tunnel)
        echo "啟動 tunneld（按 Ctrl+C 停止）..."
        sudo pymobiledevice3 remote tunneld
        ;;
    *)
        echo "iOS 17+ 虛擬定位工具"
        echo ""
        echo "用法："
        echo "  loc go <地點>          前往預設地點"
        echo "  loc set <緯度> <經度>  設定自訂座標"
        echo "  loc clear              清除模擬位置"
        echo "  loc list               列出預設地點"
        echo "  loc tunnel             啟動 tunneld"
        echo ""
        echo "範例："
        echo "  loc go taipei101"
        echo "  loc set 25.0330 121.5654"
        ;;
esac