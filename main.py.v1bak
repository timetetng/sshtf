import json
import os
import asyncio
import aiofiles
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Union, Any, Dict

# --- 配置 ---
CONFIG_PATH = "config.json"
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
async def get_index():
    """提供 index.html 前端页面"""
    if not os.path.exists("index.html"):
        return HTMLResponse(content="<h1>错误：未找到 index.html</h1>", status_code=500)
    async with aiofiles.open("index.html", 'r', encoding='utf-8') as f:
        return HTMLResponse(content=await f.read())

@app.get("/app.js", include_in_schema=False)
async def get_js():
    """提供 app.js 前端逻辑"""
    if not os.path.exists("app.js"):
        return JSONResponse(content={"error": "未找到 app.js"}, status_code=500)
    async with aiofiles.open("app.js", 'r', encoding='utf-8') as f:
        content = await f.read()
        return HTMLResponse(content=content, media_type="application/javascript")


@app.get("/style.css", include_in_schema=False)
async def get_css():
    """提供独立的 style.css 文件"""
    css_path = "style.css"
    if not os.path.exists(css_path):
        # 提供一个兜底，以防文件丢失
        return HTMLResponse(content="/* 错误: 未找到 style.css */", media_type="text/css", status_code=404)
    return FileResponse(css_path)

@app.get("/button.css", include_in_schema=False)
async def get_css():
    """提供独立的 button.css 文件"""
    css_path = "button.css"
    if not os.path.exists(css_path):
        return HTMLResponse(content="/* 错误: 未找到 button.css */", media_type="text/css", status_code=404)
    return FileResponse(css_path)

# --- 用于直接运行 (python main.py) ---
if __name__ == "__main__":
    import uvicorn
    print("--- 启动端口转发配置管理器 Web UI (V3) ---")
    print("--- 拖拽排序 + 复制功能 ---")
    print("--- 服务器运行在 http://127.0.0.1:8000 ---")
    print("--- 按 CTRL+C 停止 ---")
    uvicorn.run(app, host="127.0.0.1", port=8000)