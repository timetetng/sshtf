#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

try:
    import psutil
    from colorama import init, Fore, Style
except ImportError:
    print("错误：缺少必要的库。")
    print("请先运行: pip install psutil colorama")
    sys.exit(1)


# --- 配置 ---

# 初始化 colorama
init(autoreset=True)

# 配置文件路径
try:
    # __file__ 在 .py 文件中可用
    SCRIPT_DIR = Path(__file__).parent
except NameError:
    # 在交互式环境（如 REPL）中回退
    SCRIPT_DIR = Path.cwd()

CONFIG_PATH = SCRIPT_DIR / "config.json"
CONFIG = {}


def get_matching_ssh_processes():
    """
    扫描系统，查找所有由该脚本启动的 ssh.exe 隧道进程。
    这是通过匹配命令行参数的特定组合来实现的。
    """
    matching_processes = []
    try:
        # 迭代所有进程，请求 cmdline 信息
        all_processes = list(psutil.process_iter(['pid', 'name', 'cmdline']))
    except Exception as e:
        print(f"{Fore.RED}❌ 无法查询系统进程: {e}。可能需要管理员权限。")
        return []

    for proc in all_processes:
        try:
            # 确保进程名是 ssh.exe (不区分大小写)
            if proc.info['name'] and proc.info['name'].lower() == 'ssh.exe':
                # 将 cmdline 列表合并为字符串，以便于搜索
                cmdline_str = " ".join(proc.info['cmdline'] or [])

                # 定义我们脚本启动的隧道的独特特征
                if (
                    "-o StrictHostKeyChecking=no" in cmdline_str and
                    "-o UserKnownHostsFile=NUL" in cmdline_str and
                    "-N" in cmdline_str and  # 确保 -N 存在
                    "-L" in cmdline_str and  # 确保 -L 存在
                    "-o ServerAliveInterval=60" in cmdline_str
                ):
                    matching_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 进程可能已经结束，或者我们没有权限访问
            continue
        except Exception as e:
            # 捕获其他潜在错误
            print(f"{Fore.YELLOW}警告：检查进程 {proc.pid} 时出错: {e}")
    
    return matching_processes
# --- 全局隧道计数器 ---
# 我们使用一个全局变量来缓存隧道数量，避免在每次菜单刷新时都扫描所有进程
G_ACTIVE_TUNNEL_COUNT = 0

def update_active_tunnel_count(force_scan=True):
    """
    (昂贵的操作) 
    执行实际的进程扫描并更新全局计数器。
    """
    global G_ACTIVE_TUNNEL_COUNT
    if force_scan:
        # 强制执行昂贵的进程扫描
        G_ACTIVE_TUNNEL_COUNT = len(get_matching_ssh_processes())
    return G_ACTIVE_TUNNEL_COUNT

def get_active_tunnel_count():
    """
    (快速的操作)
    立即返回当前已知的隧道数量（从缓存中读取）。
    """
    global G_ACTIVE_TUNNEL_COUNT
    return G_ACTIVE_TUNNEL_COUNT

def kill_running_ssh_tunnels(no_pause=False):
    """
    查找并终止所有匹配的 SSH 隧道进程。
    """
    print(f"{Fore.YELLOW}--- 正在搜索并关闭所有活动隧道 ---")
    
    # 扫描操作在这里执行一次
    tunnel_processes = get_matching_ssh_processes()
    
    if not tunnel_processes:
        print("隧道清理完毕。")
        # 确保计数器同步
        update_active_tunnel_count(force_scan=False) # 强制设为0（因为len是0）
        G_ACTIVE_TUNNEL_COUNT = 0 # 或者直接设为0
        time.sleep(1)
        return

    print(f"正在尝试关闭 {len(tunnel_processes)} 个匹配的隧道...")
    
    for proc in tunnel_processes:
        try:
            # proc.kill() 相当于 Stop-Process -Force
            proc.kill()
            print(f"{Fore.GREEN}✅ 已关闭隧道 (PID: {proc.pid})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"{Fore.RED}❌ 关闭隧道 (PID: {proc.pid}) 时出错: 进程已不存在或无权限。")
        except Exception as e:
            print(f"{Fore.RED}❌ 关闭隧道 (PID: {proc.pid}) 时出错: {e}")

    print("--------------------")
    print("隧道清理完毕。")
    
    # !!! 修改点：清理后立即强制更新全局计数器 !!!
    update_active_tunnel_count(force_scan=True)
    
    if not no_pause:
        # 仅在非退出时（即用户手动选'k'时）暂停
        input("按 Enter 键继续...")

    print(f"正在尝试关闭 {len(tunnel_processes)} 个匹配的隧道...")
    
    for proc in tunnel_processes:
        try:
            # proc.kill() 相当于 Stop-Process -Force
            proc.kill()
            print(f"{Fore.GREEN}✅ 已关闭隧道 (PID: {proc.pid})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"{Fore.RED}❌ 关闭隧道 (PID: {proc.pid}) 时出错: 进程已不存在或无权限。")
        except Exception as e:
            print(f"{Fore.RED}❌ 关闭隧道 (PID: {proc.pid}) 时出错: {e}")

    print("--------------------")
    print("隧道清理完毕。")
    
    if not no_pause:
        # 仅在非退出时（即用户手动选'k'时）暂停
        input("按 Enter 键继续...")


# --- 辅助函数 ---

def clear_screen():
    """
    清除终端屏幕。
    """
    os.system('cls' if os.name == 'nt' else 'clear')

def is_port_in_use(port: int) -> bool:
    """
    检查本地端口是否处于 LISTEN 状态。
    (相当于 Get-NetTCPConnection -LocalPort $port -State Listen)
    """
    try:
        for conn in psutil.net_connections(kind='tcp'):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                return True
    except psutil.AccessDenied:
        print(f"{Fore.YELLOW}警告：无权限检查所有端口连接。端口检查可能不准确。")
    except Exception as e:
        print(f"{Fore.YELLOW}警告：检查端口 {port} 时出错: {e}。")
    return False


def start_tunnel(server_ip: str, ssh_user: str, local_port: int, remote_port: int, selected_service: dict = None):
    """
    处理端口检查、自动递增并启动 SSH 进程。
    """
    print()
    print(f"{Fore.CYAN}🔎 正在检查本地端口 {local_port} 是否可用...")
    
    original_local_port = local_port
    
    # 循环检查端口，如果被占用则自动 +1
    while is_port_in_use(local_port):
        print(f"{Fore.YELLOW}❌ 端口 {local_port} 已经被占用。")
        local_port += 1
        print(f"{Fore.YELLOW}➡️ 正在尝试下一个可用端口: {local_port}...")

    if original_local_port != local_port:
        print(f"{Fore.GREEN}✅ 本地端口 {local_port} 可用 (已从 {original_local_port} 自动调整)。")
    else:
        print(f"{Fore.GREEN}✅ 本地端口 {local_port} 可用。")
    print()

    print(f"{Fore.CYAN}🚀 正在后台启动端口转发...")
    print(f"   - 服务器地址: {server_ip}")
    print(f"   - 远程端口: {remote_port}")
    print(f"   - 本地端口: {local_port}")
    print(f"   - 连接保持间隔: 60 秒")
    print()
    
    # 构建 ssh.exe 命令参数列表
    ssh_args = [
        "ssh.exe",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-N",  # 不执行远程命令
        "-L", f"{local_port}:localhost:{remote_port}", # 转发
        f"{ssh_user}@{server_ip}",
        "-o", "ServerAliveInterval=60"
    ]
    
    # === 启动后台进程 (相当于 Start-Process -WindowStyle Hidden) ===
    try:
        # 在 Windows 上，使用 CREATE_NO_WINDOW 标志来隐藏窗口
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        # 使用 Popen 启动进程，并将 stdin/out/err 重定向到 DEVNULL
        # 这使其成为一个完全分离的后台进程
        process = subprocess.Popen(
            ssh_args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags
        )
        
        print(f"{Fore.GREEN}✅ 隧道已在后台启动 (PID: {process.pid})。")
        print(f"{Fore.YELLOW}   【重要】此模式要求使用 [SSH 密钥] 进行免密登录。")
        print(f"{Fore.YELLOW}   如果连接失败 (如需密码)，后台进程会静默退出。")
        time.sleep(0.25) # 250ms 应该足够
        update_active_tunnel_count(force_scan=True)
    except FileNotFoundError:
        print(f"{Fore.RED}❌ 启动 SSH 进程失败: 未找到 'ssh.exe'。")
        print(f"   请确保 ssh.exe (通常随 Git for Windows 或 OpenSSH) 在您的系统 PATH 中。")
    except Exception as e:
        print(f"{Fore.RED}❌ 启动 SSH 进程失败: {e}")
    
    print()

    # --- 自动打开 URL 和显示登录信息 ---
    if selected_service and selected_service.get('autoOpenUrl'):
        url_template = selected_service.get('urlTemplate', '')
        # 使用 Python 的 .format() 替代 PowerShell 的 -f
        final_url = url_template.format(local_port) 
        
        print(f"(现在你可以通过 {final_url} 访问服务了)")
        print()

        login_info = selected_service.get('loginInfo')
        if login_info and isinstance(login_info, dict):
            print(f"{Fore.CYAN}--- 登录信息 ---")
            
            # 按特定顺序显示已知键
            if 'username' in login_info:
                print(f"   用户名: {Fore.YELLOW}{login_info['username']}")
            if 'password' in login_info:
                print(f"   密  码: {Fore.YELLOW}{login_info['password']}")
            if 'token' in login_info:
                print(f"   登录Token: {Fore.YELLOW}{login_info['token']}")
            
            # 显示其他自定义键
            known_keys = {'username', 'password', 'token', 'type'}
            for key, value in login_info.items():
                if key not in known_keys:
                    print(f"   {key}: {Fore.YELLOW}{value}")
            
            print(f"{Fore.CYAN}----------------")
            print()
        
        # 启动浏览器 (Start-Process $finalUrl)
        try:
            webbrowser.open(final_url)
        except Exception as e:
            print(f"{Fore.RED}❌ 自动打开浏览器失败: {e}")


# --- 菜单循环 ---

def service_menu(selected_host: dict):
    """
    显示并处理特定主机的服务菜单。
    """
    global CONFIG
    
    while True:
        clear_screen()
        host_name = selected_host.get('hostName', 'N/A')
        print(f"{Fore.GREEN}===========================================")
        print(f"{Fore.GREEN}   主机: {host_name}")
        # === 修改点：确保调用的是 get_active_tunnel_count (不带 's') ===
        print(f"{Fore.CYAN}   (当前共 {get_active_tunnel_count()} 个活动隧道)")
        print(f"{Fore.GREEN}===========================================")

        # 动态生成服务菜单
        services = selected_host.get('services', [])
        for i, service in enumerate(services):
            print(f" {i + 1}. {service.get('serviceName', 'N/A')} "
                  f"(本地: {service.get('localPort')} -> 远程: {service.get('remotePort')})")
        
        print(" c. 自定义转发")
        print(f"{Fore.YELLOW} k. 清理所有隧道")
        print(" b. 返回上一级")
        print(" q. 退出 (并关闭所有隧道)")
        print(f"{Fore.GREEN}===========================================")
        print()
        
        service_choice_input = input("请选择要启动的服务: ").strip().lower()

        if service_choice_input == 'q':
            kill_running_ssh_tunnels(no_pause=True)
            sys.exit(0)
        
        if service_choice_input == 'b':
            return  # 跳出循环，返回主机菜单
        
        if service_choice_input == 'k':
            kill_running_ssh_tunnels(no_pause=False)
            continue # 清理后返回服务菜单

        # --- 变量初始化 ---
        local_port = 0
        remote_port = 0
        selected_service = None
        server_ip = selected_host.get('serverIP')
        ssh_user = selected_host.get('sshUser')

        if not server_ip or not ssh_user:
            print(f"{Fore.RED}配置错误：主机 {host_name} 缺少 'serverIP' 或 'sshUser'。")
            time.sleep(3)
            continue

        try:
            if service_choice_input == 'c':
                # --- 自定义转发逻辑 ---
                custom_input = input("请输入自定义转发 (格式: 端口号 或 本地端口:远程端口): ").strip()

                if custom_input.isdigit():
                    local_port = int(custom_input)
                    remote_port = int(custom_input)
                elif ':' in custom_input:
                    parts = custom_input.split(':')
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        local_port = int(parts[0])
                        remote_port = int(parts[1])
                    else:
                        raise ValueError("无效的 '本地:远程' 格式。")
                else:
                    raise ValueError("无效的端口格式。")

            elif service_choice_input.isdigit():
                # --- 预定义服务逻辑 ---
                choice_index = int(service_choice_input) - 1
                if 0 <= choice_index < len(services):
                    selected_service = services[choice_index]
                    remote_port = int(selected_service.get('remotePort', 0))
                    local_port = int(selected_service.get('localPort', 0))
                    if not remote_port or not local_port:
                        raise ValueError(f"服务 '{selected_service.get('serviceName')}' 配置中缺少端口。")
                else:
                    raise ValueError("选择的数字无效。")
            
            else:
                # --- 无效输入 ---
                raise ValueError("无效的选择。")

            # --- 端口检查和转发逻辑 (公共逻辑块) ---
            start_tunnel(server_ip, ssh_user, local_port, remote_port, selected_service)

        except ValueError as e:
            print(f"{Fore.RED}输入错误: {e} 请重新输入。")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"{Fore.RED}发生意外错误: {e}")
            time.sleep(3)
            continue

        input("\n操作完成，按 Enter 键返回服务菜单...")

def main_menu():
    """
    显示主菜单（主机选择）。
    """
    global CONFIG
    
    hosts = CONFIG.get('hosts', [])
    if not hosts:
        print(f"{Fore.RED}错误：配置文件 'config.json' 中没有找到 'hosts' 列表。")
        input("按 Enter 键退出...")
        sys.exit(1)

    while True:
        clear_screen()
        print(f"{Fore.BLUE}===========================================")
        print(f"{Fore.BLUE}         请选择要连接的主机")
        # === 修改点：确保调用的是 get_active_tunnel_count (不带 's') ===
        print(f"{Fore.CYAN}         (当前有 {get_active_tunnel_count()} 个活动隧道)")
        print(f"{Fore.BLUE}===========================================")

        # 动态生成主机菜单
        for i, host_info in enumerate(hosts):
            print(f" {i + 1}. {host_info.get('hostName', 'N/A')}")
        
        print(" q. 退出 (并关闭所有隧道)")
        print(f"{Fore.BLUE}===========================================")
        print()
        
        host_choice_input = input("请输入您的选择: ").strip().lower()

        if host_choice_input == 'q':
            kill_running_ssh_tunnels(no_pause=True)
            sys.exit(0)

        # 验证输入
        if host_choice_input.isdigit():
            try:
                choice_index = int(host_choice_input) - 1
                if 0 <= choice_index < len(hosts):
                    selected_host = hosts[choice_index]
                    # === 进入服务菜单 ===
                    service_menu(selected_host)
                else:
                    print(f"{Fore.RED}无效的选择，请输入 1 到 {len(hosts)} 之间的数字。")
                    time.sleep(2)
            except ValueError:
                print(f"{Fore.RED}无效的输入，请输入一个数字。")
                time.sleep(2)
        else:
            print(f"{Fore.RED}无效的选择，请重新输入。")
            time.sleep(2)
            continue # 返回主机选择

# --- 脚本主入口 ---

if __name__ == "__main__":
    # 1. 检查配置文件
    if not CONFIG_PATH.exists():
        print(f"{Fore.RED}错误：在脚本目录下找不到配置文件 'config.json'！")
        print("请确保配置文件存在且与脚本在同一目录。")
        input("按 Enter 键退出...")
        sys.exit(1)

    # 2. 读取并解析 JSON
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
    except Exception as e:
        print(f"{Fore.RED}错误：读取或解析 'config.json' 失败: {e}")
        input("按 Enter 键退出...")
        sys.exit(1)

    # !!! 修改点：脚本启动时，执行一次昂贵的扫描 !!!
    print(f"{Fore.CYAN}正在初始化并扫描现有隧道...")
    try:
        # 强制扫描一次并更新全局计数器
        update_active_tunnel_count(force_scan=True)
        print(f"检测到 {get_active_tunnel_count()} 个由本脚本管理的活动隧道。")
        time.sleep(0.5) # 给用户一点时间看信息
    except Exception as e:
        print(f"{Fore.RED}启动时扫描隧道失败: {e}")
        time.sleep(2)


    # 3. 运行主菜单
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}检测到 Ctrl+C，正在清理并退出...")
        kill_running_ssh_tunnels(no_pause=True)
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}发生未捕获的致命错误: {e}")
        kill_running_ssh_tunnels(no_pause=True)
        sys.exit(1)