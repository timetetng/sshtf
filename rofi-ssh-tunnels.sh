#!/usr/bin/env bash

# === Rofi SSH 多级隧道菜单 ===

# --- 1. Rofi 主题配置 ---
THEME_DIR="$HOME/.config/rofi/launchers/type-6"
THEME_NAME="style-9"
THEME_FILE="$THEME_DIR/$THEME_NAME.rasi"

# --- 2. Python 后端脚本路径 ---
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PYTHON_SCRIPT="$SCRIPT_DIR/ssh_rofi.py"

# 确保文件存在
if [ ! -f "$PYTHON_SCRIPT" ]; then rofi -e "错误: 找不到 $PYTHON_SCRIPT"; exit 1; fi
if [ ! -f "$THEME_FILE" ]; then rofi -e "错误: 找不到 $THEME_FILE"; exit 1; fi

# --- 3. Rofi 辅助函数 ---
run_rofi() {
    echo -e "$1" | rofi -dmenu -p "$2" -theme "$THEME_FILE" -i -markup-rows
}
run_rofi_input() {
    rofi -dmenu -p "$1" -theme "$THEME_FILE"
}

# --- 4. 菜单逻辑 ---

# 菜单: 自定义转发
show_custom_forward_menu() {
    local host_name="$1"
    local prompt="󰌖  $host_name (L:R 或 Port)"
    local ports_str=$(run_rofi_input "$prompt")
    
    if [ -n "$ports_str" ]; then
        "$PYTHON_SCRIPT" --start-custom-tunnel "$host_name" "$ports_str" &
    fi
}

# 菜单: 服务列表
show_service_menu() {
    local host_name_full="$1"
    local host_name=$(echo "$host_name_full" | sed 's/󰪥  //')
    
    local prompt="  $host_name"
    local options=$("$PYTHON_SCRIPT" --list-services "$host_name")
    
    local choice=$(run_rofi "$options" "$prompt")
    
    case "$choice" in
        "󰌍  返回上一级")
            main_menu
            ;;
        "󰔰  清理所有隧道")
            "$PYTHON_SCRIPT" --kill-all &
            main_menu
            ;;
        "󰌖  自定义转发")
            show_custom_forward_menu "$host_name"
            show_service_menu "$host_name_full" # 动作完成后返回服务菜单
            ;;
        "") # Esc
            exit 0
            ;;
        *)  # 这是一个服务
            "$PYTHON_SCRIPT" --start-tunnel "$host_name" "$choice" &
            show_service_menu "$host_name_full" # 动作完成后返回服务菜单
            ;;
    esac
}

# 菜单: 主机列表 (主入口)
main_menu() {
    local tunnel_count=$("$PYTHON_SCRIPT" --get-tunnel-count)
    local prompt="󰪥  SSH 主机 ( $tunnel_count 隧道 )"
    
    local options=$("$PYTHON_SCRIPT" --list-hosts)
    local choice=$(run_rofi "$options" "$prompt")
    
    case "$choice" in
        "󰔰  清理所有隧道")
            "$PYTHON_SCRIPT" --kill-all &
            main_menu
            ;;
        "󰩈  退出")
            exit 0
            ;;
        "") # Esc
            exit 0
            ;;
        *)  # 这是一个主机
            show_service_menu "$choice"
            ;;
    esac
}

# --- 脚本入口 ---
main_menu
