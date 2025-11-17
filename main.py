import json
import os
import asyncio
import aiofiles
import argparse
import pathlib 
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Union, Any, Dict
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
# --- 配置 ---
CONFIG_PATH = SCRIPT_DIR / "config.json"
file_lock = asyncio.Lock()

# --- Pydantic 模型 ---

class Service(BaseModel):
    serviceName: str
    remotePort: int
    localPort: int
    autoOpenUrl: bool
    urlTemplate: str
    loginInfo: Optional[Dict[str, Any]] = None 

class Host(BaseModel):
    hostName: str
    serverIP: str
    sshUser: str
    services: List[Service] = []

class Config(BaseModel):
    hosts: List[Host]

# --- FastAPI 应用实例 ---
app = FastAPI(title="端口转发配置管理器 API (V3)")

# --- 辅助函数：异步读写 config.json ---

async def get_config() -> Config:
    """异步读取、解析并校验 config.json"""
    async with file_lock:
        if not os.path.exists(CONFIG_PATH):
            return Config(hosts=[])
        
        async with aiofiles.open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = await f.read()
            if not content:
                 return Config(hosts=[])
            try:
                data = json.loads(content)
                return Config.model_validate(data)
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="config.json 文件格式错误 (非 JSON)")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"解析 config.json 出错: {e}")

async def save_config(config: Config):
    """异步将配置对象写回 config.json"""
    async with file_lock:
        async with aiofiles.open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            await f.write(config.model_dump_json(indent=2))

# --- 【新增】SSH Config 导入逻辑 ---
async def import_ssh_config(ssh_config_path_str: str):
    """
    从 .ssh/config 文件解析主机信息并导入到 config.json
    """
    ssh_config_path = pathlib.Path(ssh_config_path_str)
    if not ssh_config_path.is_file():
        print(f"❌ 错误: 路径 '{ssh_config_path_str}' 不是一个有效文件。")
        return
    
    print(f"ℹ️ 正在从 '{ssh_config_path_str}' 读取 SSH 配置...")
    
    parsed_hosts = []
    current_host_data = {}

    try:
        # 使用 aiofiles 异步读取
        async with aiofiles.open(ssh_config_path, 'r', encoding='utf-8') as f:
            async for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue # 跳过空行和注释

                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    continue
                
                key = parts[0].lower()
                value = parts[1]

                if key == 'host':
                    # 遇到新的 Host 块
                    if current_host_data.get('hostName') and current_host_data.get('serverIP') and current_host_data.get('sshUser'):
                        # 保存上一个有效的主机
                        parsed_hosts.append(Host(**current_host_data, services=[]))
                    
                    # 开始新的主机 (我们使用 'Host' 字段作为 Pydantic 模型中的 'hostName')
                    current_host_data = {'hostName': value}
                    
                elif key == 'hostname' and current_host_data:
                    # 'HostName' 字段作为 Pydantic 模型中的 'serverIP' (实际IP/域名)
                    current_host_data['serverIP'] = value
                    
                elif key == 'user' and current_host_data:
                    current_host_data['sshUser'] = value
                
                # (忽略 Port 和其他字段)
    
        # 保存文件读取后的最后一个主机
        if current_host_data.get('hostName') and current_host_data.get('serverIP') and current_host_data.get('sshUser'):
            parsed_hosts.append(Host(**current_host_data, services=[]))
            
    except Exception as e:
        print(f"❌ 解析 SSH 配置文件时出错: {e}")
        return

    if not parsed_hosts:
        print("ℹ️ 未在 SSH 配置文件中找到任何(完整 Host/HostName/User)的主机条目。")
        return

    print(f"✅ 成功解析到 {len(parsed_hosts)} 个主机。正在合并到 config.json...")

    # --- 合并逻辑 ---
    try:
        config = await get_config()
        existing_hostnames = {h.hostName for h in config.hosts}
        new_hosts_added = 0
        
        for new_host in parsed_hosts:
            if new_host.hostName not in existing_hostnames:
                config.hosts.append(new_host)
                existing_hostnames.add(new_host.hostName)
                new_hosts_added += 1
            else:
                print(f"ℹ️ 跳过已存在的主机: {new_host.hostName}")

        if new_hosts_added > 0:
            await save_config(config)
            print(f"✅ 成功导入 {new_hosts_added} 个新主机到 {CONFIG_PATH}。")
        else:
            print("ℹ️ 没有新主机被导入（可能都已存在）。")
            
    except Exception as e:
        print(f"❌ 写入 config.json 时出错: {e}")


# --- API Endpoints ---

# 1. 获取所有配置
@app.get("/api/config", response_model=Config, tags=["Config"])
async def api_get_config():
    """获取完整的配置信息"""
    return await get_config()

# 2. 【新增】保存完整配置 (用于拖拽排序)
@app.put("/api/config", response_model=Config, tags=["Config"])
async def api_update_config(config: Config):
    """接收一个完整的配置对象并覆盖保存"""
    try:
        await save_config(config)
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {e}")

# 3. 添加新主机
@app.post("/api/hosts", response_model=Host, tags=["Hosts"])
async def api_add_host(host: Host):
    """添加一个新主机"""
    config = await get_config()
    if any(h.hostName == host.hostName for h in config.hosts):
        raise HTTPException(status_code=400, detail="主机名已存在")
    
    config.hosts.append(host)
    await save_config(config)
    return host

# 4. 删除主机
@app.delete("/api/hosts/{host_name}", response_model=dict, tags=["Hosts"])
async def api_delete_host(host_name: str):
    """根据主机名删除一个主机"""
    config = await get_config()
    original_count = len(config.hosts)
    config.hosts = [h for h in config.hosts if h.hostName != host_name]
    
    if len(config.hosts) == original_count:
        raise HTTPException(status_code=404, detail="未找到指定的主机名")
        
    await save_config(config)
    return {"message": f"主机 '{host_name}' 已删除"}

# 5. 添加新服务
@app.post("/api/hosts/{host_name}/services", response_model=Service, tags=["Services"])
async def api_add_service(host_name: str, service: Service):
    """为指定的主机添加一个新服务"""
    config = await get_config()
    host_found = next((h for h in config.hosts if h.hostName == host_name), None)
            
    if not host_found:
        raise HTTPException(status_code=404, detail="未找到指定的主机名")
        
    if any(s.serviceName == service.serviceName for s in host_found.services):
         raise HTTPException(status_code=400, detail=f"主机 '{host_name}' 下已存在同名服务")
         
    host_found.services.append(service)
    await save_config(config)
    return service

# 6. 删除服务
@app.delete("/api/hosts/{host_name}/services/{service_name}", response_model=dict, tags=["Services"])
async def api_delete_service(host_name: str, service_name: str):
    """删除指定主机下的指定服务"""
    config = await get_config()
    host_found = next((h for h in config.hosts if h.hostName == host_name), None)
            
    if not host_found:
        raise HTTPException(status_code=404, detail="未找到指定的主机名")

    original_service_count = len(host_found.services)
    host_found.services = [s for s in host_found.services if s.serviceName != service_name]
    
    if len(host_found.services) == original_service_count:
         raise HTTPException(status_code=404, detail="未找到指定的服务名")
         
    await save_config(config)
    return {"message": f"服务 '{service_name}' 已从 '{host_name}' 删除"}

# 7. 修改服务
@app.put("/api/hosts/{host_name}/services/{original_service_name}", response_model=Service, tags=["Services"])
async def api_update_service(host_name: str, original_service_name: str, updated_service: Service):
    """修改指定主机下的指定服务"""
    config = await get_config()
    host_found = next((h for h in config.hosts if h.hostName == host_name), None)
            
    if not host_found:
        raise HTTPException(status_code=404, detail="未找到指定的主机名")

    service_index = -1
    for i, s in enumerate(host_found.services):
        if s.serviceName == original_service_name:
            service_index = i
            break
            
    if service_index == -1:
        raise HTTPException(status_code=404, detail="未找到要修改的原始服务名")

    new_name = updated_service.serviceName
    if new_name != original_service_name and any(s.serviceName == new_name for s in host_found.services):
        raise HTTPException(status_code=400, detail=f"服务名 '{new_name}' 已在当前主机下存在")

    host_found.services[service_index] = updated_service
    await save_config(config)
    return updated_service


# --- 静态文件服务 (前端 UI) ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
async def get_index():
    """提供 index.html 前端页面"""
    file_path = SCRIPT_DIR / "index.html" # 【修改】
    if not file_path.exists(): # 【修改】
        return HTMLResponse(content=f"<h1>错误：未找到 {file_path.name}</h1>", status_code=500)
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f: # 【修改】
        return HTMLResponse(content=await f.read())

@app.get("/app.js", include_in_schema=False)
async def get_js():
    """提供 app.js 前端逻辑"""
    file_path = SCRIPT_DIR / "app.js" # 【修改】
    if not file_path.exists(): # 【修改】
        return JSONResponse(content={"error": f"未找到 {file_path.name}"}, status_code=500)
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f: # 【修改】
        content = await f.read()
        return HTMLResponse(content=content, media_type="application/javascript")


@app.get("/style.css", include_in_schema=False)
async def get_style_css(): # 【修改】函数名
    """提供独立的 style.css 文件"""
    css_path = SCRIPT_DIR / "style.css" # 【修改】
    if not css_path.exists(): # 【修改】
        # 提供一个兜底，以防文件丢失
        return HTMLResponse(content="/* 错误: 未找到 style.css */", media_type="text/css", status_code=404)
    return FileResponse(css_path)

@app.get("/button.css", include_in_schema=False)
async def get_button_css(): # 【修改】函数名
    """提供独立的 button.css 文件"""
    css_path = SCRIPT_DIR / "button.css" # 【修改】
    if not css_path.exists(): # 【修改】
        return HTMLResponse(content="/* 错误: 未找到 button.css */", media_type="text/css", status_code=404)
    return FileResponse(css_path)

# --- 用于直接运行 (python main.py) ---
if __name__ == "__main__":
    
    # --- 【修改】添加命令行参数解析 ---
    parser = argparse.ArgumentParser(
        description="SSH 隧道转发管理器 Web UI.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-p", "--path",
        dest="ssh_config_path",
        type=str,
        help="指定 .ssh/config 文件的路径以导入主机。\n如果提供此参数，将只执行导入任务，不会启动 Web 服务器。"
    )
    args = parser.parse_args()

    if args.ssh_config_path:
        # --- 执行导入任务 ---
        print("--- 正在执行 SSH Config 导入任务 ---")
        try:
            # 因为 import_ssh_config 是 async, 我们需要用 asyncio.run()
            asyncio.run(import_ssh_config(args.ssh_config_path))
        except Exception as e:
            print(f"❌ 导入过程中发生意外错误: {e}")
        print("--- 导入任务完成 ---")
    else:
        # --- 正常启动 Web 服务器 ---
        import uvicorn
        print("--- 启动端口转发配置管理器 Web UI (V3) ---")
        print("--- 拖拽排序 + 复制功能 ---")
        print("--- 服务器运行在 http://127.0.0.1:8000 ---")
        print("--- 按 CTRL+C 停止 ---")
        uvicorn.run(app, host="127.0.0.1", port=8000)
