#!/usr/bin/env bash

# === SSH 主菜单 (启动器) ===
#
# 这个脚本会启动一个“菜单的菜单”，让你选择：
# 1. 启动我们的“自定义隧道管理器”（多级菜单）
# 2. 启动 Rofi 的“原生 SSH 模式”

# --- 1. Rofi 主题 ---
dir="$HOME/.config/rofi/launchers/type-6"
theme='style-9'
THEME_FILE="${dir}/${theme}.rasi"

# --- 2. 脚本路径 ---
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
# (指向我们刚刚创建的多级菜单 Bash 脚本)
TUNNEL_SCRIPT="$SCRIPT_DIR/rofi-ssh-tunnels.sh"

# --- 3. 菜单选项 (使用 Nerd Font 图标) ---
OPTIONS="  SSH\n"
OPTIONS+="󰪥  自定义隧道"
# --- 4. 运行 Rofi (dmenu 模式) ---
choice=$(echo -e "$OPTIONS" | rofi -dmenu -p "SSH 选择器" -theme "$THEME_FILE" -i -markup-rows)

# --- 5. 处理选择 ---
case "$choice" in
    "󰪥  自定义隧道")
        # 执行我们的多级菜单脚本
        exec "$TUNNEL_SCRIPT"
        ;;
    "  SSH")
        # 执行 Rofi 的原生 ssh 模式
        rofi -show ssh -theme "$THEME_FILE"
        ;;
    *)
        # 按 Esc 退出
        exit 0
        ;;
esac
