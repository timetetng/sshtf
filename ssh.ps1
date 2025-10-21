# ======================================================
# 配置文件 
# 脚本会读取同目录下的 config.json 文件
# ======================================================
$configPath = Join-Path -Path $PSScriptRoot -ChildPath "config.json"

# ======================================================
# === 进程管理函数 (WMI/CIM) ===
# ======================================================

function Get-MatchingSshProcesses {
    <#
    .SYNOPSIS
    扫描系统，查找所有由该脚本启动的 ssh.exe 隧道进程。
    这是通过匹配命令行参数的特定组合来实现的。
    #>
    
    # 查找所有 ssh.exe 进程
    try {
        # 使用 CIM (适用于 PS 5.1 及更高版本)
        $processes = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction Stop
    } catch {
        Write-Host "❌ 无法查询系统进程 (Get-CimInstance)。可能需要管理员权限。" -ForegroundColor Red
        return @()
    }

    # 定义我们脚本启动的隧道的独特特征
    # 我们使用 -like (通配符匹配) 来忽略参数的确切顺序或路径
    $matchingProcesses = $processes | Where-Object {
        $cmd = $_.CommandLine
        
        # 确保这些特征都存在于命令行中
        ($cmd -like "*-o StrictHostKeyChecking=no*") -and 
        ($cmd -like "*-o UserKnownHostsFile=NUL*") -and 
        ($cmd -like "*-N -L*") -and # -N (不执行远程命令) 和 -L (转发)
        ($cmd -like "*-o ServerAliveInterval=60*") # 保持连接
    }
    
    return $matchingProcesses
}

function Get-ActiveTunnelsCount {
    <#
    .SYNOPSIS
    返回当前系统中匹配的活动隧道数量。
    #>
    return (Get-MatchingSshProcesses).Count
}

function Kill-RunningSshTunnels {
    <#
    .SYNOPSIS
    查找并终止所有匹配的 SSH 隧道进程。
    .PARAMETER NoPause
    如果提供此开关，函数执行完毕后不会暂停等待用户按 Enter。
    #>
    param (
        [switch]$NoPause
    )
    
    Write-Host "--- 正在搜索并关闭所有活动隧道 ---" -ForegroundColor Yellow
    
    $tunnelProcesses = Get-MatchingSshProcesses
    
    if ($tunnelProcesses.Count -eq 0) {
        Write-Host "隧道清理完毕。"
        Start-Sleep -Seconds 1
        return
    }

    Write-Host "正在尝试关闭 $($tunnelProcesses.Count) 个匹配的隧道..."
    
    foreach ($process in $tunnelProcesses) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-Host "✅ 已关闭隧道 (PID: $($process.ProcessId))" -ForegroundColor Green
            # 调试时可取消注释下一行
            # Write-Host "   (Cmd: $($process.CommandLine))" -ForegroundColor Gray
        } catch {
            Write-Host "❌ 关闭隧道 (PID: $($process.ProcessId)) 时出错: $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    Write-Host "--------------------"
    Write-Host "隧道清理完毕。"
    
    if (-not $NoPause) {
        # 仅在非退出时（即用户手动选'k'时）暂停
        Read-Host "按 Enter 键继续..."
    }
}


# === 脚本主逻辑 ===

# 检查配置文件是否存在
if (-not (Test-Path $configPath)) {
    Write-Host "错误：在脚本目录下找不到配置文件 'config.json'！" -ForegroundColor Red
    Write-Host "请确保配置文件存在且与脚本在同一目录。"
    Read-Host "按 Enter 键退出..."
    exit
}

# 读取并解析 JSON 配置文件
$config = Get-Content -Path $configPath -Raw | ConvertFrom-Json

# 使用一个无限循环来持续显示主机选择菜单
while ($true) {
    Clear-Host
    Write-Host "===========================================" -ForegroundColor Blue
    Write-Host "        请选择要连接的主机" -ForegroundColor Blue
    # === 修改点：调用新函数 ===
    Write-Host "        (当前有 $(Get-ActiveTunnelsCount) 个活动隧道)" -ForegroundColor Cyan
    Write-Host "===========================================" -ForegroundColor Blue

    # 动态生成主机菜单
    for ($i = 0; $i -lt $config.hosts.Count; $i++) {
        $hostInfo = $config.hosts[$i]
        Write-Host " $($i + 1). $($hostInfo.hostName)"
    }
    Write-Host " q. 退出 (并关闭所有隧道)"
    Write-Host "===========================================" -ForegroundColor Blue
    Write-Host

    # 读取用户的主机选择
    $hostChoiceInput = Read-Host "请输入您的选择"

    if ($hostChoiceInput -eq 'q') {
        Kill-RunningSshTunnels -NoPause # 退出前清理 (不暂停)
        exit
    }

    # 验证输入是否为有效的数字
    if ($hostChoiceInput -match "^\d+$" -and [int]$hostChoiceInput -ge 1 -and [int]$hostChoiceInput -le $config.hosts.Count) {
        $selectedHost = $config.hosts[[int]$hostChoiceInput - 1]
    } else {
        Write-Host "无效的选择，请重新输入。" -ForegroundColor Red
        Start-Sleep -Seconds 2
        continue # 返回主机选择菜单
    }

    # 进入服务选择循环
    while ($true) {
        Clear-Host
        Write-Host "===========================================" -ForegroundColor Green
        Write-Host "   主机: $($selectedHost.hostName)" -ForegroundColor Green
        # === 修改点：调用新函数 ===
        Write-Host "   (当前共 $(Get-ActiveTunnelsCount) 个活动隧道)" -ForegroundColor Cyan
        Write-Host "===========================================" -ForegroundColor Green

        # 动态生成服务菜单
        for ($i = 0; $i -lt $selectedHost.services.Count; $i++) {
            $service = $selectedHost.services[$i]
            Write-Host " $($i + 1). $($service.serviceName) (本地: $($service.localPort) -> 远程: $($service.remotePort))"
        }
        Write-Host " c. 自定义转发"
        Write-Host " k. 清理所有隧道" -ForegroundColor Yellow
        Write-Host " b. 返回上一级"
        Write-Host " q. 退出 (并关闭所有隧道)"
        Write-Host "===========================================" -ForegroundColor Green
        Write-Host

        $serviceChoiceInput = Read-Host "请选择要启动的服务"

        if ($serviceChoiceInput -eq 'q') {
            Kill-RunningSshTunnels -NoPause # 退出前清理 (不暂停)
            exit
        }
        if ($serviceChoiceInput -eq 'b') {
            break # 跳出当前服务选择循环，返回主机选择
        }
        
        if ($serviceChoiceInput -eq 'k') {
            Kill-RunningSshTunnels # 清理 (默认会暂停)
            continue # 返回服务菜单
        }

        # --- 变量初始化 ---
        $localPort = 0
        $remotePort = 0
        $selectedService = $null
        $serverIP = $selectedHost.serverIP
        $sshUser = $selectedHost.sshUser

        if ($serviceChoiceInput -eq 'c') {
            # --- 自定义转发逻辑 ---
            $customInput = Read-Host "请输入自定义转发 (格式: 端口号 或 本地端口:远程端口)"

            if ($customInput -match "^\d+$") {
                $localPort = [int]$customInput
                $remotePort = [int]$customInput
            } elseif ($customInput -match "^(\d+):(\d+)$") {
                $localPort = [int]$matches[1]
                $remotePort = [int]$matches[2]
            } else {
                Write-Host "无效的端口格式。" -ForegroundColor Red
                Start-Sleep -Seconds 2
                continue
            }

        } elseif ($serviceChoiceInput -match "^\d+$" -and [int]$serviceChoiceInput -ge 1 -and [int]$serviceChoiceInput -le $selectedHost.services.Count) {
            # --- 预定义服务逻辑 ---
            $selectedService = $selectedHost.services[[int]$serviceChoiceInput - 1]
            $remotePort = $selectedService.remotePort
            $localPort = $selectedService.localPort
        } else {
            # --- 无效输入 ---
            Write-Host "无效的选择，请重新输入。" -ForegroundColor Red
            Start-Sleep -Seconds 2
            continue
        }


        # --- 端口检查和转发逻辑 (公共逻辑块) ---
        
        Write-Host
        Write-Host "🔎 正在检查本地端口 $localPort 是否可用..." -ForegroundColor Cyan

        while (Get-NetTCPConnection -LocalPort $localPort -State Listen -ErrorAction SilentlyContinue) {
            Write-Host "❌ 端口 $localPort 已经被占用。" -ForegroundColor Yellow
            $localPort++
            Write-Host "➡️ 正在尝试下一个可用端口: $localPort..." -ForegroundColor Yellow
        }

        Write-Host "✅ 本地端口 $localPort 可用。" -ForegroundColor Green
        Write-Host

        Write-Host "🚀 正在后台启动端口转发..." -ForegroundColor Cyan
        Write-Host "   - 服务器地址: $serverIP"
        Write-Host "   - 远程端口: $remotePort"
        Write-Host "   - 本地端口: $localPort"
        Write-Host "   - 连接保持间隔: 60 秒"
        Write-Host
        
        $sshArgs = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -N -L $($localPort):localhost:$($remotePort) $($sshUser)@$($serverIP) -o ServerAliveInterval=60"

        # === 修改点：不再需要捕获到列表，但保留 -PassThru 以显示PID ===
        try {
            # 仍然使用 -PassThru 来获取刚启动进程的PID，以便显示
            $process = Start-Process -FilePath "ssh.exe" -ArgumentList $sshArgs -WindowStyle Hidden -PassThru -ErrorAction Stop
            
            # 我们不再将 $process 添加到任何列表
            Write-Host "✅ 隧道已在后台启动 (PID: $($process.Id))。" -ForegroundColor Green
            Write-Host "   【重要】此模式要求使用 [SSH 密钥] 进行免密登录。" -ForegroundColor Yellow
            Write-Host "   如果连接失败 (如需密码)，后台进程会静默退出。" -ForegroundColor Yellow
        } catch {
             Write-Host "❌ 启动 SSH 进程失败: $($_.Exception.Message)" -ForegroundColor Red
             Write-Host "   请确保 ssh.exe 在您的系统 PATH 中。"
        }
        
        Write-Host

        # 如果配置了自动打开URL
        if ($null -ne $selectedService -and $selectedService.autoOpenUrl) {
            $finalUrl = $selectedService.urlTemplate -f $localPort
            Write-Host "(现在你可以通过 $finalUrl 访问服务了)"
            Write-Host

            if ($null -ne $selectedService.loginInfo) {
                
                $loginProperties = $selectedService.loginInfo.PSObject.Properties
                
                if ($loginProperties.Count -gt 0) {
                    Write-Host "--- 登录信息 ---" -ForegroundColor Cyan
                    
                    $knownKeys = @('username', 'password', 'token')
                    
                    if ($selectedService.loginInfo.PSObject.Properties.Name -contains 'username') {
                        Write-Host "   用户名: " -NoNewline
                        Write-Host $selectedService.loginInfo.username -ForegroundColor Yellow
                    }
                    if ($selectedService.loginInfo.PSObject.Properties.Name -contains 'password') {
                        Write-Host "   密  码: " -NoNewline
                        Write-Host $selectedService.loginInfo.password -ForegroundColor Yellow
                    }
                    if ($selectedService.loginInfo.PSObject.Properties.Name -contains 'token') {
                        Write-Host "   登录Token: " -NoNewline
                        Write-Host $selectedService.loginInfo.token -ForegroundColor Yellow
                    }
                    
                    foreach ($prop in $loginProperties) {
                        if ($prop.Name -notin $knownKeys -and $prop.Name -ne 'type') {
                            Write-Host "   $($prop.Name): " -NoNewline
                            Write-Host $prop.Value -ForegroundColor Yellow
                        }
                    }
                    
                    Write-Host "----------------" -ForegroundColor Cyan
                    Write-Host
                }
            }

            Start-Process $finalUrl
        }

        Read-Host "操作完成，按 Enter 键返回服务菜单..."
    }
}