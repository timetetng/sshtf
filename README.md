# sshtf - SSH 隧道转发管理器

`sshtf` 是一个用于管理和启动多主机、多服务 SSH 隧道转发的工具。它将远程服务器上的端口通过 SSH 隧道安全地转发到您的本地计算机，方便您访问远程服务。本项目包含一个 Web UI 用于配置管理，以及命令行脚本用于快速启动隧道。

`sshtf` is an SSH tunnel forwarding management tool designed to help users easily manage and launch service port forwarding to multiple remote hosts. It provides a web-based user interface (Web UI) for conveniently adding, modifying, deleting, and sorting host and service configurations, saving them in real-time to a config.json file. Additionally, it includes Python and PowerShell command-line scripts that allow users to quickly select and launch preset SSH tunnels through an interactive menu, securely mapping remote service ports to the local machine, thus simplifying the process of accessing remote services. The tool supports features like automatic port detection, background execution, connection keep-alive, and automatic URL opening.

## ✨ 功能特性

* **Web UI 配置管理**:
    * 通过友好的网页界面 (基于 FastAPI 和原生 JavaScript) 添加、修改、删除主机和其下的服务配置。
    * 支持拖拽排序主机和服务列表。
    * 支持折叠/展开主机卡片和服务添加表单。
    * 主题切换。
    * 配置文件 (`config.json`) 实时更新。
* **命令行隧道启动**:
    * 提供 Python (`ssh.py`) 和 PowerShell (`ssh.ps1`) 两种脚本，通过菜单选择主机和服务来启动隧道。
    * 支持自定义端口转发输入 (`本地端口` 或 `本地端口:远程端口`)。
    * **自动端口检测与递增**: 如果配置的本地端口已被占用，脚本会自动尝试下一个可用端口。
    * **后台运行**: SSH 隧道进程在后台静默运行。
    * **连接保持**: 自动设置 `ServerAliveInterval` 保持 SSH 连接活跃。
    * **自动打开 URL**: 可配置在隧道启动后自动在浏览器中打开服务对应的本地 URL。
    * **登录信息提示**: 可配置并显示服务的登录凭据（用户名、密码、Token 等）。
    * **隧道清理**: 提供选项来查找并关闭所有由脚本启动的活动隧道进程。
* **配置灵活**:
    * 通过简单的 `config.json` 文件管理所有主机和服务信息。
    * 支持为每个服务配置详细的登录信息（键值对形式）。
* **跨平台兼容**:
    * Web UI 可在任何现代浏览器中访问。
    * Python 命令行脚本可在 Windows, macOS, Linux 上运行 (需 `ssh.exe` 在 PATH 中)。
    * PowerShell 脚本主要适用于 Windows 环境。

## ⚙️ 系统要求

* **Python**: 版本 >= 3.12
* **包管理器 (推荐)**: [`uv`](https://github.com/astral-sh/uv) (用于快速安装依赖) 或 `pip`.
* **SSH 客户端**: 需要 `ssh.exe` (或 `ssh`) 可执行文件在系统的 `PATH` 环境变量中。 (通常随 Git for Windows, OpenSSH 或操作系统自带)
* **SSH 密钥认证**: 命令行脚本 (`ssh.py`, `ssh.ps1`) **要求** 您已经配置了到目标服务器的 SSH 密钥免密登录。如果需要输入密码，后台进程会静默失败。

## 🚀 安装

建议使用 `uv` 作为包管理器以获得更快的安装体验。

1.  **克隆仓库 (如果您还没做)**:
    ```bash
    git clone <your-repository-url>
    cd sshtf
    ```

2.  **安装依赖**:
    ```bash
    uv sync
    ```
    或者，如果您使用 `pip`:
    ```bash
    # (可选) 创建并激活虚拟环境
    # python -m venv .venv
    # source .venv/bin/activate  # Linux/macOS
    # .\.venv\Scripts\activate   # Windows PowerShell
    
    pip install -r requirements.lock # 如果您导出了 requirements.txt 或 .lock 文件
    # 或者根据 pyproject.toml 手动安装
    # pip install aiofiles colorama "fastapi[all]" psutil pydantic uvicorn
    ```

## 🛠️ 使用方法

### 1. Web UI (用于管理配置)

通过 Web 界面可以方便地添加、编辑、删除和排序主机及服务配置。

* **启动 Web 服务器**:
    ```bash
    uv run main.py
    ```
    或者 (如果您没有使用 uv run):
    ```bash
    python main.py
    ```
* **访问**: 在浏览器中打开 `http://127.0.0.1:8000`。
* **操作**:
    * 添加新主机。
    * 点击主机卡片上的 "添加服务" 按钮为该主机添加转发规则。
    * 点击服务旁的 "修改"、"删除"、"复制" 按钮进行操作。
    * 拖动主机卡片的标题栏或服务项本身进行排序。
    * 点击主机标题栏左侧的图标折叠/展开该主机下的服务列表。

    *注意*: 所有更改会实时保存到项目根目录下的 `config.json` 文件中。

### 2. 命令行脚本 (用于启动隧道)

使用命令行脚本可以通过交互式菜单快速选择并启动配置好的 SSH 隧道。

* **使用 Python 脚本**:
    ```bash
    uv run ssh.py
    ```
    或者:
    ```bash
    python ssh.py
    ```
* **使用 PowerShell 脚本 (Windows)**:
    ```powershell
    .\ssh.ps1
    ```

* **操作**:
    1.  脚本会首先列出 `config.json` 中配置的所有主机。
    2.  输入数字选择一个主机。
    3.  接着会列出该主机下配置的所有服务，以及自定义转发(`c`)、清理隧道(`k`)、返回(`b`)和退出(`q`)选项。
    4.  输入数字选择一个预定义的服务，或输入 `c` 进行自定义端口转发。
    5.  脚本会检查本地端口是否可用，如果被占用则自动尝试下一个端口。
    6.  启动 `ssh.exe` 进程在后台建立隧道。
    7.  如果配置了自动打开 URL 和登录信息，则会相应地执行。
    8.  按 Enter 返回服务菜单。
    9.  选择 `k` 可以关闭所有由脚本启动的隧道。
    10. 选择 `b` 返回主机选择菜单。
    11. 选择 `q` 会先关闭所有隧道然后退出脚本。

* **建议**: 为了方便从任何位置启动命令行脚本，可以考虑为其设置系统别名或将其路径添加到 `PATH` 环境变量中。

    * **例如 (PowerShell - 临时)**:
        ```powershell
        Set-Alias sshtf C:\path\to\your\sshtf\ssh.ps1 
        # 然后直接运行 sshtf
        ```
    * **例如 (Bash/Zsh - 临时)**:
        ```bash
        alias sshtf='python /path/to/your/sshtf/ssh.py'
        # 然后直接运行 sshtf
        ```
        (将别名添加到您的 `.bashrc` 或 `.zshrc` 文件中以使其永久生效)

## 📄 配置文件 (`config.json`)

程序的核心配置存储在 `config.json` 文件中。Web UI 会自动管理此文件。其基本结构如下：

```json
{
  "hosts": [
    {
      "hostName": "示例主机1", // 主机的友好名称
      "serverIP": "192.168.1.100", // SSH 服务器的 IP 或域名
      "sshUser": "your_user", // SSH 登录用户名
      "services": [
        {
          "serviceName": "Web 服务 A", // 服务的友好名称
          "remotePort": 8080,        // 远程服务器上的服务端口
          "localPort": 9001,         // 要映射到的本地端口
          "autoOpenUrl": true,       // 是否自动打开浏览器
          "urlTemplate": "http://localhost:{0}", // 打开的 URL 模板, {0} 会被替换为最终的本地端口
          "loginInfo": {             // 可选：登录信息 (键值对)
            "username": "admin",
            "password": "password123",
            "提示": "这是额外的提示信息" 
          }
        },
        {
          "serviceName": "数据库 B",
          "remotePort": 3306,
          "localPort": 3307,
          "autoOpenUrl": false,
          "urlTemplate": "mysql://user:pass@localhost:{0}/dbname",
          "loginInfo": null
        }
      ]
    },
    {
      "hostName": "示例主机2",
      "serverIP": "example.com",
      "sshUser": "dev",
      "services": [] // 可以暂时没有服务
    }
  ]
}