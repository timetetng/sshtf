document.addEventListener('DOMContentLoaded', () => {
    // --- 元素获取 ---
    const configContent = document.getElementById('config-content');
    const formAddHost = document.getElementById('form-add-host');
    const loadingIndicator = document.getElementById('loading');
    // 修改点：将 ID 指向新按钮的 ID
    const btnToggleTheme = document.getElementById('btn-toggle-theme-new'); 
    const addHostSection = document.getElementById('add-host-section');
    const btnToggleAddHost = document.getElementById('btn-toggle-add-host');
    
    // 获取模板
    const serviceFormTemplate = document.getElementById('template-service-form');
    const kvRowTemplate = document.getElementById('template-kv-row');
    // 用于存储从 API 获取的最新配置，方便“修改”和“拖拽”时读取
    let currentConfig = { hosts: [] };

    const API_BASE_URL = '/api';

    // --- 【新增】主题切换逻辑 ---
    const applyTheme = (theme) => {
        if (theme === 'dark') {
            document.body.dataset.theme = 'dark';
        } else {
            document.body.dataset.theme = 'light';
        }
    };
    
    const toggleTheme = () => {
        const currentTheme = document.body.dataset.theme || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        localStorage.setItem('config-theme', newTheme);
        applyTheme(newTheme);
    };

    btnToggleTheme.addEventListener('click', toggleTheme);

    // 加载时应用保存的主题
    const savedTheme = localStorage.getItem('config-theme');
    if (savedTheme) {
        applyTheme(savedTheme);
    }
    
    // --- 【新增】“添加主机”表单折叠逻辑 ---
    btnToggleAddHost.addEventListener('click', () => {
        const isCollapsed = addHostSection.classList.toggle('collapsed');
        btnToggleAddHost.textContent = isCollapsed ? '显示' : '隐藏';
        localStorage.setItem('add-host-collapsed', isCollapsed ? 'true' : 'false');
    });

    // 加载时恢复“添加主机”折叠状态
    if (localStorage.getItem('add-host-collapsed') === 'true') {
        addHostSection.classList.add('collapsed');
        btnToggleAddHost.textContent = '显示';
    }


    // --- 工具函数 ---
    const showLoading = (show) => {
        loadingIndicator.style.display = show ? 'block' : 'none';
    };

    const showAlert = (message, isError = false) => {
        alert(message); 
        if (isError) {
            console.error(message);
        }
    };

    // --- API 调用封装 ---
    const api = {
        getConfig: async () => {
            const response = await fetch(`${API_BASE_URL}/config`);
            if (!response.ok) throw new Error(`无法加载配置: ${response.statusText}`);
            return await response.json();
        },
        updateConfig: async (configData) => {
             const response = await fetch(`${API_BASE_URL}/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(configData),
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || '保存排序失败');
            }
            return await response.json();
        },
        addHost: async (hostData) => {
            const response = await fetch(`${API_BASE_URL}/hosts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(hostData),
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || '添加主机失败');
            }
            return await response.json();
        },
        deleteHost: async (hostName) => {
            const response = await fetch(`${API_BASE_URL}/hosts/${encodeURIComponent(hostName)}`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || '删除主机失败');
            }
            return await response.json();
        },
        addService: async (hostName, serviceData) => {
            const response = await fetch(`${API_BASE_URL}/hosts/${encodeURIComponent(hostName)}/services`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(serviceData),
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || '添加服务失败');
            }
            return await response.json();
        },
        deleteService: async (hostName, serviceName) => {
            const response = await fetch(`${API_BASE_URL}/hosts/${encodeURIComponent(hostName)}/services/${encodeURIComponent(serviceName)}`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || '删除服务失败');
            }
            return await response.json();
        },
        updateService: async (hostName, originalServiceName, serviceData) => {
            const response = await fetch(`${API_BASE_URL}/hosts/${encodeURIComponent(hostName)}/services/${encodeURIComponent(originalServiceName)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(serviceData),
            });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || '更新服务失败');
            }
            return await response.json();
        }
    };

    // --- K-V 构建器辅助函数 ---
    const addKvRow = (builderElement, key = '', value = '') => {
        const rowClone = kvRowTemplate.content.cloneNode(true);
        const row = rowClone.querySelector('.kv-row');
        const select = row.querySelector('.kv-key-select');
        const customInput = row.querySelector('.kv-key-custom');
        const valueInput = row.querySelector('.kv-value');

        valueInput.value = value;
        const isPreset = Array.from(select.options).some(opt => opt.value === key);
        
        if (isPreset) {
            select.value = key;
            customInput.style.display = 'none';
        } else if (key) {
            select.value = 'custom';
            customInput.style.display = 'block';
            customInput.value = key;
        } else {
             customInput.style.display = 'none';
        }

        builderElement.appendChild(row);
    };

    const populateKvBuilder = (builderElement, loginInfo) => {
        builderElement.innerHTML = '';
        if (loginInfo && typeof loginInfo === 'object') {
            for (const [key, value] of Object.entries(loginInfo)) {
                const displayValue = (typeof value === 'object' || value === null) ? JSON.stringify(value) : String(value);
                addKvRow(builderElement, key, displayValue);
            }
        }
    };

    const readKvBuilder = (builderElement) => {
        const rows = builderElement.querySelectorAll('.kv-row');
        if (rows.length === 0) {
            return null;
        }
        
        const loginInfo = {};
        let allKeysValid = true;
        
        rows.forEach(row => {
            const select = row.querySelector('.kv-key-select');
            const customInput = row.querySelector('.kv-key-custom');
            const valueInput = row.querySelector('.kv-value');
            
            let key = (select.value === 'custom') ? customInput.value.trim() : select.value;
            const value = valueInput.value;
            
            if (!key) {
                allKeysValid = false;
            } else if (loginInfo.hasOwnProperty(key)) {
                // 处理重复的 key
                allKeysValid = false;
            } else {
                loginInfo[key] = value;
            }
        });

        if (!allKeysValid) {
            showAlert('登录信息中存在无效或重复的“自定义键”，请填写或删除该行。', true);
            return 'INVALID';
        }
        
        return loginInfo;
    };


    // --- 【重构】显示服务表单 ---
    const showServiceForm = ({ mode, hostCardEl, serviceItemEl = null, serviceData = null }) => {
        const hostName = hostCardEl.dataset.host;
        
        // 1. 移除该主机下任何已打开的“添加”表单
        hostCardEl.querySelector('.service-form-container[data-mode="add"]')?.remove();
        
        // 2. 准备表单
        const formClone = serviceFormTemplate.content.cloneNode(true);
        const formContainer = formClone.querySelector('.service-form-container');
        const form = formContainer.querySelector('form.service-form');
        
        form.dataset.mode = mode;
        form.dataset.hostName = hostName;
        formContainer.dataset.mode = mode; 
        
        formContainer.querySelector('.host-name-placeholder').textContent = hostName;

        // 3. 填充数据
        if (mode === 'edit' && serviceData) {
            formContainer.querySelector('.form-title').textContent = '修改服务';
            form.dataset.originalServiceName = serviceData.serviceName;
            
            form.querySelector('.serviceName').value = serviceData.serviceName;
            form.querySelector('.remotePort').value = serviceData.remotePort;
            form.querySelector('.localPort').value = serviceData.localPort;
            form.querySelector('.urlTemplate').value = serviceData.urlTemplate;
            form.querySelector('.autoOpenUrl').checked = serviceData.autoOpenUrl;
            
            populateKvBuilder(form.querySelector('.login-info-builder'), serviceData.loginInfo);
            
            // 插入表单并隐藏原内容
            serviceItemEl.querySelector('.service-content').style.display = 'none';
            serviceItemEl.appendChild(formClone);

        } else { // 'add' 模式 (包括 'copy')
            formContainer.querySelector('.form-title').textContent = '添加新服务';
            
            if (serviceData) { // 这是 'copy' 逻辑
                form.querySelector('.serviceName').value = serviceData.serviceName + " (复制)"; // 预填充复制
                form.querySelector('.remotePort').value = serviceData.remotePort;
                form.querySelector('.localPort').value = serviceData.localPort;
                form.querySelector('.urlTemplate').value = serviceData.urlTemplate;
                form.querySelector('.autoOpenUrl').checked = serviceData.autoOpenUrl;
                populateKvBuilder(form.querySelector('.login-info-builder'), serviceData.loginInfo);
            }
            
            // 插入到主机卡片底部
            hostCardEl.appendChild(formClone);
        }
    };

    // --- 渲染逻辑 ---

    // 渲染登录信息
    const renderLoginInfo = (loginInfo) => {
        if (!loginInfo || Object.keys(loginInfo).length === 0) {
            return '<span class="service-login">无登录信息</span>';
        }
        if (loginInfo.username) {
            return `<span class="service-login">用户: ${loginInfo.username}</span>`;
        }
        if (loginInfo.token) {
            return `<span class="service-login">Token: ***</span>`;
        }
        if (loginInfo.password) {
             return `<span class="service-login">密码: ***</span>`;
        }
        const firstKey = Object.keys(loginInfo)[0];
        return `<span class="service-login">${firstKey}: ...</span>`;
    };

    // 渲染单个服务
    const renderService = (hostName, service) => {
        return `
            <div class="service-item" data-host="${hostName}" data-service="${service.serviceName}">
                <div class="service-content">
                    <div class="service-details">
                        <strong>${service.serviceName}</strong>
                        (L: ${service.localPort} -> R: ${service.remotePort})
                        <div class="service-url">URL: ${service.urlTemplate || 'N/A'} (AutoOpen: ${service.autoOpenUrl})</div>
                        ${renderLoginInfo(service.loginInfo)}
                    </div>
                    <div class="service-actions">
                        <button class="btn btn-secondary btn-copy-service">复制</button>
                        <button class="btn btn-secondary btn-edit-service">修改</button>
                        <button class="btn btn-danger btn-delete-service">删除</button>
                    </div>
                </div>
            </div>
        `;
    };

    // 【修改】渲染单个主机 (添加折叠按钮和默认折叠类)
    const renderHost = (host) => {
        const hostCard = document.createElement('div');
        // 修改：默认添加 collapsed 类
        hostCard.className = 'host-card collapsed'; 
        hostCard.setAttribute('data-host', host.hostName);
        
        let servicesHtml = host.services.map(service => renderService(host.hostName, service)).join('');
        if (!host.services || host.services.length === 0) {
            servicesHtml = '<p>暂无服务。请添加一个。</p>';
        }

        // 修改：更新 innerHTML 结构，添加折叠按钮
        hostCard.innerHTML = `
            <div class="host-header">
                <div>
                    <button class="btn btn-icon btn-toggle-host-collapse"></button> 
                    <h3>${host.hostName}</h3>
                    <div class="host-meta">${host.sshUser}@${host.serverIP}</div>
                </div>
                <div>
                    <button class="btn btn-primary btn-show-add-service">添加服务</button>
                    <button class="btn btn-danger btn-delete-host">删除主机</button>
                </div>
            </div>
            <div class="service-list">
                ${servicesHtml}
            </div>
        `;
        return hostCard;
    };

    // 加载并渲染所有配置
    const loadAndRenderConfig = async () => {
        showLoading(true);
        configContent.innerHTML = ''; // 清空
        try {
            const config = await api.getConfig();
            currentConfig = config; // 保存到全局
            
            if (!config.hosts || config.hosts.length === 0) {
                configContent.innerHTML = '<p>暂无主机配置，请在下方添加一个新主机。</p>';
            } else {
                config.hosts.forEach(host => {
                    const hostEl = renderHost(host);
                    configContent.appendChild(hostEl);
                });
            }
            
            // 渲染完成后初始化拖拽
            initSortables();
            
        } catch (error) {
            showAlert(`加载失败: ${error.message}`, true);
        } finally {
            showLoading(false);
        }
    };

    // --- 拖拽排序逻辑 ---
    
    // 查找数据对象
    const findHostInConfig = (hostName) => currentConfig.hosts.find(h => h.hostName === hostName);
    const findServiceInHost = (host, serviceName) => host.services.find(s => s.serviceName === serviceName);

    const handleHostReorder = async (evt) => {
        const hostCards = Array.from(evt.target.children);
        const newHostOrder = hostCards.map(card => card.dataset.host).filter(Boolean);
        
        const newHosts = newHostOrder.map(hostName => findHostInConfig(hostName));
        currentConfig.hosts = newHosts;
        
        try {
            await api.updateConfig(currentConfig);
        } catch (error) {
            showAlert(`主机排序保存失败: ${error.message}，将刷新页面。`, true);
            await loadAndRenderConfig(); // 失败时回滚
        }
    };
    
    const handleServiceReorder = async (evt) => {
        const hostCard = evt.from.closest('.host-card');
        const hostName = hostCard.dataset.host;
        const host = findHostInConfig(hostName);
        if (!host) return;

        const serviceItems = Array.from(evt.target.children);
        // 修正：从 evt.target.children 过滤掉可能的 <p> 标签
        const newServiceOrder = serviceItems
            .map(item => item.dataset ? item.dataset.service : null)
            .filter(Boolean);

        const newServices = newServiceOrder.map(serviceName => findServiceInHost(host, serviceName));
        host.services = newServices;
        
        try {
            await api.updateConfig(currentConfig);
        } catch (error) {
            showAlert(`服务排序保存失败: ${error.message}，将刷新页面。`, true);
            await loadAndRenderConfig(); // 失败时回滚
        }
    };

    // 【修改】初始化拖拽 (更新 handle 和 filter)
    const initSortables = () => {
        // 1. 初始化主机卡片排序
        new Sortable(configContent, {
            animation: 150,
            handle: '.host-header', // 修改：使用 header 作为拖拽句柄
            filter: '.btn', // 修改：忽略句柄内的 .btn 元素，使其可点击
            preventOnFilter: true, // 修改：确保 filter 生效
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            onEnd: handleHostReorder
        });
        
        // 2. 初始化每个主机内部的服务列表排序
        document.querySelectorAll('.service-list').forEach(list => {
            new Sortable(list, {
                animation: 150,
                handle: '.service-item',
                filter: '.btn', // 同样过滤服务项中的按钮
                preventOnFilter: true,
                ghostClass: 'sortable-ghost',
                chosenClass: 'sortable-chosen',
                onEnd: handleServiceReorder
            });
        });
    };

    // --- 事件监听 ---

    // 1. 添加主机
    formAddHost.addEventListener('submit', async (e) => {
        e.preventDefault();
        const hostData = {
            hostName: document.getElementById('hostName').value.trim(),
            serverIP: document.getElementById('serverIP').value.trim(),
            sshUser: document.getElementById('sshUser').value.trim(),
            services: []
        };

        if (!hostData.hostName || !hostData.serverIP || !hostData.sshUser) {
            showAlert('主机名、IP 和 SSH 用户均不能为空', true);
            return;
        }

        try {
            await api.addHost(hostData);
            showAlert('主机添加成功！');
            formAddHost.reset();
            // 优化：如果添加表单是折叠的，在成功后保持折叠
            // (目前不需要，刷新就好)
            await loadAndRenderConfig();
        } catch (error) {
            showAlert(`添加主机失败: ${error.message}`, true);
        }
    });

    // 2. configContent 上的全局事件委托 (修改：增加折叠逻辑)
    configContent.addEventListener('click', async (e) => {
        const target = e.target;
        
        // --- 【新增】主机卡片折叠/展开 ---
        if (target.classList.contains('btn-toggle-host-collapse')) {
            const hostCard = target.closest('.host-card');
            if (hostCard) {
                hostCard.classList.toggle('collapsed');
            }
            return; // 处理完毕，终止
        }

        const hostCard = target.closest('.host-card');
        const serviceItem = target.closest('.service-item');

        // 2a. 删除主机
        if (target.classList.contains('btn-delete-host')) {
            const hostName = hostCard.dataset.host;
            if (confirm(`确定要删除主机 "${hostName}" 及其所有服务吗？`)) {
                try {
                    await api.deleteHost(hostName);
                    showAlert('主机删除成功');
                    await loadAndRenderConfig();
                } catch (error) {
                    showAlert(`删除主机失败: ${error.message}`, true);
                }
            }
        }

        // 2b. 删除服务
        if (target.classList.contains('btn-delete-service')) {
            const hostName = serviceItem.dataset.host;
            const serviceName = serviceItem.dataset.service;
            if (confirm(`确定要删除主机 "${hostName}" 下的服务 "${serviceName}" 吗？`)) {
                try {
                    await api.deleteService(hostName, serviceName);
                    showAlert('服务删除成功');
                    await loadAndRenderConfig();
                } catch (error) {
                    showAlert(`删除服务失败: ${error.message}`, true);
                }
            }
        }
        
        // 2c. 显示“添加服务”表单
        if (target.classList.contains('btn-show-add-service')) {
            showServiceForm({
                mode: 'add',
                hostCardEl: hostCard
            });
        }
        
        // 2d. 显示“修改服务”表单
        if (target.classList.contains('btn-edit-service')) {
            const host = findHostInConfig(serviceItem.dataset.host);
            const service = findServiceInHost(host, serviceItem.dataset.service);
            if (service) {
                showServiceForm({
                    mode: 'edit',
                    hostCardEl: hostCard,
                    serviceItemEl: serviceItem,
                    serviceData: service
                });
            }
        }
        
        // 2e. “复制服务”
        if (target.classList.contains('btn-copy-service')) {
            const host = findHostInConfig(serviceItem.dataset.host);
            const service = findServiceInHost(host, serviceItem.dataset.service);
            if (service) {
                showServiceForm({
                    mode: 'add',
                    hostCardEl: hostCard,
                    serviceData: service // 传入原服务数据
                });
            }
        }

        // 2f. 取消“添加/修改服务”
        if (target.classList.contains('btn-cancel-service')) {
            const formContainer = target.closest('.service-form-container');
            if (serviceItem) { // 'edit' 模式
                serviceItem.querySelector('.service-content').style.display = 'flex';
                formContainer.remove();
            } else { // 'add' 模式
                formContainer.remove();
            }
        }
        
        // 2g. K-V 构建器：添加行
        if (target.classList.contains('btn-add-kv-pair')) {
            const builder = target.closest('.full-width').querySelector('.login-info-builder');
            addKvRow(builder);
        }
        
        // 2h. K-V 构建器：删除行
        if (target.classList.contains('btn-remove-kv-pair')) {
            target.closest('.kv-row').remove();
        }
    });
    
    // 3. K-V 构建器：下拉菜单切换
    configContent.addEventListener('change', (e) => {
        if (e.target.classList.contains('kv-key-select')) {
            const row = e.target.closest('.kv-row');
            const customInput = row.querySelector('.kv-key-custom');
            customInput.style.display = (e.target.value === 'custom') ? 'block' : 'none';
        }
    });

    // 4. 提交“添加/修改服务”表单 (使用事件委托)
    configContent.addEventListener('submit', async (e) => {
        if (e.target.classList.contains('service-form')) {
            e.preventDefault();
            const form = e.target;
            const hostName = form.dataset.hostName;
            const mode = form.dataset.mode;
            const originalServiceName = form.dataset.originalServiceName;
            
            const loginInfo = readKvBuilder(form.querySelector('.login-info-builder'));
            if (loginInfo === 'INVALID') {
                return;
            }

            const serviceData = {
                serviceName: form.querySelector('.serviceName').value.trim(),
                remotePort: parseInt(form.querySelector('.remotePort').value, 10),
                localPort: parseInt(form.querySelector('.localPort').value, 10),
                autoOpenUrl: form.querySelector('.autoOpenUrl').checked,
                urlTemplate: form.querySelector('.urlTemplate').value,
                loginInfo: loginInfo
            };
            
            if (!serviceData.serviceName || isNaN(serviceData.remotePort) || isNaN(serviceData.localPort)) {
                showAlert('服务名和端口不能为空且必须是数字', true);
                return;
            }
            
            try {
                if (mode === 'add') {
                    await api.addService(hostName, serviceData);
                    showAlert('服务添加成功');
                } else if (mode === 'edit') {
                    await api.updateService(hostName, originalServiceName, serviceData);
                    showAlert('服务修改成功');
                }
                await loadAndRenderConfig(); // 统一重新加载
            } catch (error) {
                showAlert(`操作失败: ${error.message}`, true);
            }
        }
    });

    // --- 初始加载 ---
    loadAndRenderConfig();
});