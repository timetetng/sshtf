#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
import argparse
import shlex  # 用于安全地构建 shell 命令

try:
    import psutil
except ImportError:
    # 如果 psutil 缺失，我们无法做任何事。Rofi 会显示这个错误。
    print("󰩈  退出 (错误: 缺少 'psutil' 库)")
    sys.exit(1)


# --- 配置 ---

# 配置文件路径
try:
    SCRIPT_DIR = Path(__file__).parent
except NameError:
    SCRIPT_DIR = Path.cwd()

CONFIG_PATH = SCRIPT_DIR / "config.json"
CONFIG = {}


# --- Rofi/Notify-Send 辅助函数 ---

def rofi_notify(title, message, icon="dialog-information"):
    """
    通过 notify-send 发送桌面通知。
    """
    try:
        # 使用 shlex.quote 来安全地处理可能包含特殊字符的字符串
        subprocess.run([
            "notify-send",
            "-a", "SSHTunnelScript",  # 应用名称
            "-i", icon,              # 图标
            title,
            message
        ], check=True, timeout=5)
    except Exception as e:
        # Fallback if notify-send fails (e.g., not installed)
        print(f"NOTIFY-ERROR: {e}", file=sys.stderr)


# --- 核心 SSH 隧道逻辑 (已修改为使用 notify-send) ---

def get_matching_ssh_processes():
    """
    扫描系统，查找所有由该脚本启动的 ssh.exe 隧道进程。
    (此函数与原版基本相同，仅移除 colorama)
    """
    matching_processes = []
    try:
        all_processes = list(psutil.process_iter(['pid', 'name', 'cmdline']))
    except Exception as e:
        # 无法在 Rofi 中打印，只能在 stderr 中记录
        print(f"❌ 无法查询系统进程: {e}。可能需要管理员权限。", file=sys.stderr)
        return []

    for proc in all_processes:
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'ssh':
                cmdline_str = " ".join(proc.info['cmdline'] or [])
                if (
                    "-o StrictHostKeyChecking=no" in cmdline_str and
                    "-o UserKnownHostsFile=NUL" in cmdline_str and
                    "-N" in cmdline_str and
                    "-L" in cmdline_str and
                    "-o ServerAliveInterval=60" in cmdline_str
                ):
                    matching_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception as e:
            print(f"警告：检查进程 {proc.pid} 时出错: {e}", file=sys.stderr)
    
    return matching_processes

G_ACTIVE_TUNNEL_COUNT = 0

def update_active_tunnel_count(force_scan=True):
    global G_ACTIVE_TUNNEL_COUNT
    if force_scan:
        G_ACTIVE_TUNNEL_COUNT = len(get_matching_ssh_processes())
    return G_ACTIVE_TUNNEL_COUNT

def get_active_tunnel_count():
    global G_ACTIVE_TUNNEL_COUNT
    return G_ACTIVE_TUNNEL_COUNT

def kill_running_ssh_tunnels(no_pause=False):
    """
    查找并终止所有匹配的 SSH 隧道进程。
    (已修改：使用 notify-send 替换 print/input)
    """
    rofi_notify("SSH 隧道", "正在搜索并关闭所有活动隧道...", "network-transmit")
    
    tunnel_processes = get_matching_ssh_processes()
    
    if not tunnel_processes:
        rofi_notify("SSH 隧道", "隧道清理完毕 (未找到活动进程)。", "network-idle")
        update_active_tunnel_count(force_scan=False)
        G_ACTIVE_TUNNEL_COUNT = 0
        return

    count = len(tunnel_processes)
    rofi_notify("SSH 隧道", f"正在关闭 {count} 个匹配的隧道...", "network-transmit")
    
    killed_count = 0
    for proc in tunnel_processes:
        try:
            proc.kill()
            killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass # 进程已消失或无权限
        except Exception as e:
            print(f"❌ 关闭隧道 (PID: {proc.pid}) 时出错: {e}", file=sys.stderr)

    rofi_notify("SSH 隧道", f"隧道清理完毕。成功关闭 {killed_count}/{count} 个。", "network-idle")
    update_active_tunnel_count(force_scan=True)

# --- 辅助函数 (已修改) ---

def is_port_in_use(port: int) -> bool:
    """
    检查本地端口是否处于 LISTEN 状态。
    (已修改：移除 print 警告)
    """
    try:
        for conn in psutil.net_connections(kind='tcp'):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                return True
    except (psutil.AccessDenied, Exception) as e:
        # 在 Rofi 脚本中，我们最好保持静默，只在 stderr 打印
        print(f"警告：检查端口 {port} 时出错: {e}。", file=sys.stderr)
    return False


def start_tunnel(server_ip: str, ssh_user: str, local_port: int, remote_port: int, selected_service: dict = None):
    """
    处理端口检查、自动递增并启动 SSH 进程。
    (已修改：使用 notify-send 替换 print/input)
    """
    original_local_port = local_port
    
    while is_port_in_use(local_port):
        rofi_notify("端口检查", f"端口 {local_port} 被占用，正在尝试 {local_port + 1}...", "dialog-warning")
        local_port += 1

    if original_local_port != local_port:
        rofi_notify("端口调整", f"本地端口已从 {original_local_port} 调整为 {local_port}", "dialog-information")

    rofi_notify("SSH 隧道", f"🚀 正在启动: L:{local_port} -> R:{remote_port} @ {server_ip}", "network-transmit")

    ssh_args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-N",
        "-L", f"{local_port}:localhost:{remote_port}",
        f"{ssh_user}@{server_ip}",
        "-o", "ServerAliveInterval=60"
    ]
    
    try:
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        process = subprocess.Popen(
            ssh_args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags
        )
        
        rofi_notify("SSH 隧道", f"✅ 隧道已在后台启动 (PID: {process.pid})。\n(如需密码会静默失败，请检查密钥)", "network-wired")
        time.sleep(0.25)
        update_active_tunnel_count(force_scan=True)
    
    except FileNotFoundError:
        rofi_notify("启动失败", "未找到 'ssh' 命令。\n请确保 OpenSSH 在系统 PATH 中。", "dialog-error")
    except Exception as e:
        rofi_notify("启动失败", str(e), "dialog-error")
        return # 启动失败，后续步骤无需执行

    # --- 自动打开 URL 和显示登录信息 ---
    if selected_service and selected_service.get('autoOpenUrl'):
        url_template = selected_service.get('urlTemplate', '')
        final_url = url_template.format(local_port)
        
        login_info_str = f"即将打开: {final_url}\n\n"
        
        login_info = selected_service.get('loginInfo')
        if login_info and isinstance(login_info, dict):
            # 按特定顺序显示
            if 'username' in login_info:
                login_info_str += f"用户名: {login_info['username']}\n"
            if 'password' in login_info:
                login_info_str += f"密  码: {login_info['password']}\n"
            if 'token' in login_info:
                login_info_str += f"Token: {login_info['token']}\n"
            
            # 显示其他自定义键
            known_keys = {'username', 'password', 'token', 'type'}
            for key, value in login_info.items():
                if key not in known_keys:
                    login_info_str += f"{key}: {value}\n"
        
        # 通过 notify-send 显示登录信息
        rofi_notify(f"登录信息: {selected_service.get('serviceName')}", login_info_str, "dialog-password")
        
        try:
            webbrowser.open(final_url)
        except Exception as e:
            rofi_notify("浏览器错误", f"自动打开浏览器失败: {e}", "dialog-error")

# --- Rofi List Generators ---

def handle_list_hosts(config):
    """
    打印 Rofi 主菜单列表 (主机)
    """
    hosts = config.get('hosts', [])
    if not hosts:
        print("󰩈  退出 (错误: config.json 中无主机)")
        return
    
    # 打印所有主机
    for host_info in hosts:
        print(f"󰪥  {host_info.get('hostName', 'N/A')}")
    
    # 打印全局操作
    print("󰔰  清理所有隧道")
    print("󰩈  退出")

def handle_list_services(config, host_name):
    """
    打印 Rofi 服务菜单列表
    """
    host = next((h for h in config.get('hosts', []) if h.get('hostName') == host_name), None)
    if not host:
        print("󰌍  返回上一级 (错误: 未找到主机)")
        return
        
    services = host.get('services', [])
    for service in services:
        # 格式:   ServiceName  (L:80 -> R:80)
        print(f"  {service.get('serviceName', 'N/A')}  <span weight='light' size='small'><i>(L:{service.get('localPort')} -> R:{service.get('remotePort')})</i></span>")
    
    # 打印此菜单的操作
    print("󰌖  自定义转发")
    print("󰔰  清理所有隧道")
    print("󰌍  返回上一级")

# --- Rofi Action Handlers ---

def find_host_config(config, host_name):
    return next((h for h in config.get('hosts', []) if h.get('hostName') == host_name), None)

def find_service_config(host_config, service_menu_str):
    """
    从 Rofi 返回的完整菜单字符串中解析出服务名称
    """
    # service_menu_str is "  ServiceName  <span...>(L:80 -> R:80)</i></span>"
    if not service_menu_str.startswith("  "):
        return None
    
    # 1. 移除图标: "ServiceName  <span...>(L:80 -> R:80)</i></span>"
    name_and_markup = service_menu_str.split(maxsplit=1)[1]
    
    # 2. 查找 Pango 标记的开头，它分隔了名称和端口信息
    separator_index = name_and_markup.find("  <span")
    if separator_index == -1:
        # 如果没有 span 标记 (以防万一)
        separator_index = name_and_markup.rfind("  (")
        if separator_index == -1:
             # 假设只有服务名
             service_name = name_and_markup
        else:
             service_name = name_and_markup[:separator_index].strip()
    else:
        service_name = name_and_markup[:separator_index].strip()
        
    # 3. 在配置中查找该服务
    return next((s for s in host_config.get('services', []) if s.get('serviceName') == service_name), None)

def handle_start_tunnel(config, host_name, service_menu_str):
    host_config = find_host_config(config, host_name)
    if not host_config:
        rofi_notify("错误", f"未找到主机配置: {host_name}", "dialog-error")
        return

    service_config = find_service_config(host_config, service_menu_str)
    if not service_config:
        rofi_notify("错误", f"未找到服务配置: {service_menu_str}", "dialog-error")
        return
    
    try:
        start_tunnel(
            server_ip=host_config.get('serverIP'),
            ssh_user=host_config.get('sshUser'),
            local_port=int(service_config.get('localPort')),
            remote_port=int(service_config.get('remotePort')),
            selected_service=service_config
        )
    except Exception as e:
        rofi_notify("启动失败", str(e), "dialog-error")

def handle_custom_tunnel(config, host_name, ports_str):
    host_config = find_host_config(config, host_name)
    if not host_config:
        rofi_notify("错误", f"未找到主机配置: {host_name}", "dialog-error")
        return
        
    try:
        local_port, remote_port = 0, 0
        ports_str = ports_str.strip()
        
        if ports_str.isdigit():
            local_port = int(ports_str)
            remote_port = int(ports_str)
        elif ':' in ports_str:
            parts = ports_str.split(':')
            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                local_port = int(parts[0].strip())
                remote_port = int(parts[1].strip())
            else:
                raise ValueError("无效的 '本地:远程' 格式。")
        else:
            raise ValueError("无效的端口格式。")
        
        if local_port <= 0 or remote_port <= 0:
             raise ValueError("端口必须大于 0。")

        start_tunnel(
            server_ip=host_config.get('serverIP'),
            ssh_user=host_config.get('sshUser'),
            local_port=local_port,
            remote_port=remote_port,
            selected_service=None # 自定义转发没有自动打开/登录信息
        )
    except Exception as e:
         rofi_notify("自定义转发失败", str(e), "dialog-error")

# --- 脚本主入口 (由 Argparse 驱动) ---

if __name__ == "__main__":
    # 1. 立即加载配置
    if not CONFIG_PATH.exists():
        print(f"󰩈  退出 (错误: 找不到 {CONFIG_PATH})")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
    except Exception as e:
        print(f"󰩈  退出 (错误: 解析 config.json 失败: {e})")
        sys.exit(1)

    # 2. 解析命令行参数
    parser = argparse.ArgumentParser(description="SSH Tunnel Rofi Helper")
    parser.add_argument("--list-hosts", action="store_true", help="List hosts for Rofi")
    parser.add_argument("--list-services", type=str, help="List services for a host (by name)")
    parser.add_argument("--get-tunnel-count", action="store_true", help="Get active tunnel count")
    parser.add_argument("--kill-all", action="store_true", help="Kill all active tunnels")
    parser.add_argument("--start-tunnel", nargs=2, metavar=('HOST_NAME', 'SERVICE_STR'), help="Start a tunnel")
    parser.add_argument("--start-custom-tunnel", nargs=2, metavar=('HOST_NAME', 'PORTS_STR'), help="Start a custom tunnel")
    
    args = parser.parse_args()
    
    # 3. 根据参数执行动作
    try:
        if args.list_hosts:
            handle_list_hosts(CONFIG)
        elif args.list_services:
            handle_list_services(CONFIG, args.list_services)
        elif args.get_tunnel_count:
            # Rofi Prompt 需要这个，必须强制扫描
            update_active_tunnel_count(force_scan=True)
            print(get_active_tunnel_count())
        elif args.kill_all:
            kill_running_ssh_tunnels(no_pause=True)
        elif args.start_tunnel:
            handle_start_tunnel(CONFIG, args.start_tunnel[0], args.start_tunnel[1])
        elif args.start_custom_tunnel:
            handle_custom_tunnel(CONFIG, args.start_custom_tunnel[0], args.start_custom_tunnel[1])
        else:
            # 默认启动时，打印主机列表 (以防万一直接运行)
            handle_list_hosts(CONFIG)
            
    except Exception as e:
        # 最后的防线
        rofi_notify("Python 脚本致命错误", str(e), "dialog-error")
        sys.exit(1)
