// FastAPIProject/static/main.js

// 全局变量存储当前数据
let currentData = null;
let currentTask = null;
let accumulatedJSON = '';  // 累积的JSON字符串
let lastChunkTime = 0;  // 最后一次chunk更新时间

console.log('页面加载完成');

// 渲染流程卡片
function renderProcessCards(data, isRealtime = false) {
    const container = document.getElementById('process-cards');

    if (!data || !data.processes || data.processes.length === 0) {
        container.innerHTML = `
            <div class="loading-card" style="grid-column: 1 / -1;">
                <div class="loading-spinner"></div>
                <p style="color: #666;">正在加载数据，请稍候...</p>
            </div>
        `;
        return;
    }

    // 清空容器
    container.innerHTML = '';

    // 为每个工序创建卡片
    data.processes.forEach((proc, index) => {
        const card = createProcessCard(proc, index, isRealtime);
        container.appendChild(card);

        // 延迟动画效果
        setTimeout(() => {
            card.style.animationDelay = `${index * 0.1}s`;
        }, 10);
    });

    // 初始化展开/折叠功能
    initializeCardInteractions();
}

// 创建单个工序卡片
function createProcessCard(process, index, isRealtime) {
    const card = document.createElement('div');
    card.className = 'process-card';
    card.dataset.processId = process.process_id;

    const hasSteps = process.steps && process.steps.length > 0;
    const stepCount = hasSteps ? process.steps.length : 0;

    card.innerHTML = `
        <div class="card-header">
            <div class="process-number">#${process.process_id}</div>
            <div class="process-name">${process.name}</div>
        </div>
        <div class="card-body">
            <div class="process-description">${process.description || '暂无描述'}</div>
            <div class="steps-container">
                <div class="steps-header" onclick="toggleSteps(${process.process_id})">
                    <div class="steps-title">
                        <span>工步详情</span>
                        <span class="step-count">${hasSteps ? stepCount : '加载中...'}</span>
                    </div>
                    <svg class="expand-icon" id="expand-${process.process_id}">
                        <use href="#expand-icon"></use>
                    </svg>
                </div>
                <div class="steps-list" id="steps-${process.process_id}">
                    ${renderStepsList(process.steps, isRealtime)}
                </div>
            </div>
        </div>
    `;

    return card;
}

// 渲染工步列表
function renderStepsList(steps, isRealtime) {
    if (!steps || steps.length === 0) {
        return `
            <div class="step-item" style="animation-delay: 0s;">
                <div class="loading-spinner" style="width: 30px; height: 30px; margin: 10px auto;"></div>
                <p style="text-align: center; color: #666; margin: 0;">正在分解工步...</p>
            </div>
        `;
    }

    return steps.map((step, index) => `
        <div class="step-item" style="animation-delay: ${index * 0.05}s;">
            <div class="step-header">
                <div class="step-number">${step.step_id}</div>
                <div class="step-unit">${step.unit || ''}</div>
            </div>
            <div class="step-content">
                <div class="step-device">🔩 ${step.device || '未指定设备'}</div>
                <div class="step-action">${step.action || '暂无操作说明'}</div>
            </div>
        </div>
    `).join('');
}

// 切换工步展开/折叠
window.toggleSteps = function(processId) {
    const stepsList = document.getElementById(`steps-${processId}`);
    const expandIcon = document.getElementById(`expand-${processId}`);

    if (stepsList.classList.contains('expanded')) {
        // 收起：清除动态高度
        stepsList.classList.remove('expanded');
        stepsList.style.maxHeight = null;
        expandIcon.classList.remove('expanded');
        // 可选：移除滚动类
        stepsList.classList.remove('scrollable');
    } else {
        // 展开：先加 expanded 类
        stepsList.classList.add('expanded');
        expandIcon.classList.add('expanded');
        // 动态计算并设置最大高度
        const fullHeight = stepsList.scrollHeight;
        stepsList.style.maxHeight = fullHeight + 'px';

        // 如果内容高度超过某阈值（如 500px），可加滚动条
        if (fullHeight > 500) {
            stepsList.classList.add('scrollable');
        }
    }
};

// 初始化卡片交互
function initializeCardInteractions() {
    // 自动展开第一个卡片
    const firstCard = document.querySelector('.process-card');
    if (firstCard) {
        const processId = firstCard.dataset.processId;
        setTimeout(() => {
            toggleSteps(processId);
        }, 500);
    }
}

// 更新单个工序卡片的工步
function updateProcessSteps(processId, steps) {
    const stepsContainer = document.getElementById(`steps-${processId}`);
    if (stepsContainer) {
        stepsContainer.innerHTML = renderStepsList(steps, false);

        // 更新工步计数
        const card = document.querySelector(`[data-process-id="${processId}"]`);
        if (card) {
            const stepCount = card.querySelector('.step-count');
            if (stepCount) {
                stepCount.textContent = steps.length;
            }
        }
    }
}

// 渲染Excel风格表格（保持原有功能）
function renderExcelTable(data) {
    const excelWindow = document.getElementById('excel-window');
    if (!data || !data.processes) {
        excelWindow.innerHTML = '<p style="color: #666; text-align: center; padding: 20px;">等待数据...</p>';
        return;
    }

    // 扁平化数据
    const flatData = [];
    data.processes.forEach(proc => {
        if (proc.steps && proc.steps.length > 0) {
            proc.steps.forEach((step, stepIndex) => {
                flatData.push({
                    process_id: proc.process_id,
                    process_name: proc.name,
                    process_description: proc.description || '',
                    unit: step.unit || '',
                    step_id: step.step_id,
                    device: step.device || '',
                    action: step.action || '',
                    isFirstStep: stepIndex === 0,
                    totalSteps: proc.steps.length
                });
            });
        } else {
            flatData.push({
                process_id: proc.process_id,
                process_name: proc.name,
                process_description: proc.description || '',
                unit: '-',
                step_id: '-',
                device: '-',
                action: '正在分解工步...',
                isFirstStep: true,
                totalSteps: 1
            });
        }
    });

    // 构建Excel风格表格
    let html = '<table class="excel-table">';
    html += '<thead><tr>';
    html += '<th>工序ID</th>';
    html += '<th>工序名称</th>';
    html += '<th>工序描述</th>';
    html += '<th>单元</th>';
    html += '<th>步骤ID</th>';
    html += '<th>设备</th>';
    html += '<th>操作</th>';
    html += '</tr></thead><tbody>';

    let currentProcessId = null;
    flatData.forEach((row, index) => {
        html += '<tr class="step-row">';

        // 处理合并单元格
        if (row.process_id !== currentProcessId) {
            currentProcessId = row.process_id;

            // 计算需要合并的行数
            let rowspan = 1;
            for (let i = index + 1; i < flatData.length; i++) {
                if (flatData[i].process_id === currentProcessId) {
                    rowspan++;
                } else {
                    break;
                }
            }

            html += `<td rowspan="${rowspan}" class="merged process-info">${row.process_id}</td>`;
            html += `<td rowspan="${rowspan}" class="merged process-info">${row.process_name}</td>`;
            html += `<td rowspan="${rowspan}" class="merged process-info">${row.process_description}</td>`;
        }

        // 步骤相关列
        html += `<td>${row.unit}</td>`;
        html += `<td style="text-align: center;">${row.step_id}</td>`;
        html += `<td>${row.device}</td>`;
        if (row.action === '正在分解工步...') {
            html += `<td><span class="loading-text" style="color: #666; font-style: italic;">${row.action}</span></td>`;
        } else {
            html += `<td>${row.action}</td>`;
        }
        html += '</tr>';
    });

    html += '</tbody></table>';
    excelWindow.innerHTML = html;
}

// 表单提交事件
document.getElementById('taskForm').addEventListener('submit', e => {
    e.preventDefault();
    console.log('表单提交');

    const task = e.target.task.value.trim();
    if (!task) return;

    currentTask = task;  // 保存当前任务

    // 更新按钮状态
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    const submitBtn = document.querySelector('.submit-btn');
    btnText.style.display = 'none';
    btnSpinner.style.display = 'inline';
    submitBtn.disabled = true;

    // 重置UI
    document.getElementById('status').textContent = '已提交，等待服务器响应…';
    document.getElementById('progressBar').value = 0;
    document.getElementById('process-cards').innerHTML = `
        <div class="loading-card" style="grid-column: 1 / -1;">
            <div class="loading-spinner"></div>
            <p style="color: #666;">正在连接服务器...</p>
        </div>
    `;
    document.getElementById('excel-window').innerHTML = '<p style="color: #666; text-align: center; padding: 20px;">正在加载数据，请稍候...</p>';
    document.getElementById('exportExcel').style.display = 'none';
    document.getElementById('exportJson').style.display = 'none';
    document.getElementById('excel-title').textContent = '工艺工序分解结果';
    document.getElementById('update-status').style.display = 'none';
    document.getElementById('performance-info').style.display = 'none';
    document.getElementById('parallel-count').textContent = '';
    accumulatedJSON = '';
    lastChunkTime = 0;

    console.log('开始连接SSE:', `/api/decompose/stream?task=${encodeURIComponent(task)}`);

    const es = new EventSource(`/api/decompose/stream?task=${encodeURIComponent(task)}`);

    es.addEventListener('open', () => {
        console.log('SSE连接已建立');
    });

    es.addEventListener('status', evt => {
        console.log('收到status事件:', evt.data);

        // 检查是否是缓存加载
        if (evt.data.includes('缓存')) {
            console.log('检测到缓存加载模式');
            document.getElementById('status').innerHTML = evt.data + ' <span style="color: #667eea;">⚡</span>';
        } else {
            document.getElementById('status').textContent = evt.data;
        }

        // 如果是并行分解状态，显示性能提示
        if (evt.data.includes('并行分解')) {
            document.getElementById('performance-info').style.display = 'block';
            const match = evt.data.match(/并行分解 (\d+) 个工序/);
            if (match) {
                document.getElementById('parallel-count').textContent = `(同时处理 ${match[1]} 个工序)`;
            }
        }

        // 统计有多少工序包含工步
        if (evt.data.includes('已完成工序')) {
            const match = evt.data.match(/已完成工序 (\d+)\/(\d+)/);
            if (match) {
                document.getElementById('parallel-count').textContent = `(已完成 ${match[1]}/${match[2]} 个工序)`;
            }
        }
    });

    es.addEventListener('progress', evt => {
        console.log('收到progress事件:', evt.data);
        document.getElementById('progressBar').value = parseInt(evt.data, 10);
    });

    es.addEventListener('chunk', evt => {
        console.log('收到chunk事件，数据长度:', evt.data.length);

        // 检查是否是缓存加载
        if (evt.data.includes('===FINAL_JSON_START===')) {
            console.log('检测到缓存数据标记');
        }

        // 显示更新指示器
        document.getElementById('update-status').style.display = 'inline';

        // 累积JSON数据
        accumulatedJSON += evt.data + "\n";
        lastChunkTime = Date.now();

        // 延迟处理，等待完整的chunk数据
        setTimeout(() => {
            if (Date.now() - lastChunkTime >= 450) {
                tryParseAndUpdate();
            }
        }, 500);
    });

    function tryParseAndUpdate() {
        try {
            // 检查是否有最终JSON标记
            const finalJsonStart = accumulatedJSON.indexOf('===FINAL_JSON_START===');
            const finalJsonEnd = accumulatedJSON.indexOf('===FINAL_JSON_END===');

            if (finalJsonStart !== -1 && finalJsonEnd !== -1) {
                // 提取最终JSON
                const jsonContent = accumulatedJSON.substring(
                    finalJsonStart + '===FINAL_JSON_START==='.length,
                    finalJsonEnd
                ).trim();

                try {
                    const finalData = JSON.parse(jsonContent);
                    console.log('解析最终JSON成功！');
                    console.log('- 工序数:', finalData.processes.length);
                    let totalSteps = 0;
                    finalData.processes.forEach(p => {
                        if (p.steps) totalSteps += p.steps.length;
                    });
                    console.log('- 总工步数:', totalSteps);

                    currentData = finalData;
                    renderProcessCards(finalData, false);
                    renderExcelTable(finalData);
                    return;
                } catch (e) {
                    console.error('解析最终JSON失败:', e);
                }
            }

            // 如果没有最终标记，使用原来的解析逻辑
            const jsonMatches = [];
            let tempJson = '';
            let depth = 0;
            let inString = false;
            let escapeNext = false;

            for (let i = 0; i < accumulatedJSON.length; i++) {
                const char = accumulatedJSON[i];

                if (!inString) {
                    if (char === '"' && !escapeNext) inString = true;
                    else if (char === '{') {
                        if (depth === 0) tempJson = '';
                        depth++;
                    } else if (char === '}') {
                        depth--;
                        if (depth === 0 && tempJson) {
                            try {
                                const parsed = JSON.parse(tempJson + char);
                                if (parsed && parsed.processes) {
                                    jsonMatches.push(parsed);
                                }
                            } catch (e) {
                                // 继续
                            }
                        }
                    }
                } else {
                    if (char === '"' && !escapeNext) inString = false;
                }

                if (depth > 0) tempJson += char;
                escapeNext = (!escapeNext && char === '\\');
            }

            // 使用最后一个有效的JSON
            if (jsonMatches.length > 0) {
                const lastValidJson = jsonMatches[jsonMatches.length - 1];
                console.log('找到有效JSON，工序数:', lastValidJson.processes.length);

                // 统计有多少工序包含工步
                let processesWithSteps = 0;
                let totalSteps = 0;
                lastValidJson.processes.forEach(p => {
                    if (p.steps && p.steps.length > 0) {
                        processesWithSteps++;
                        totalSteps += p.steps.length;
                    }
                });
                console.log(`包含工步的工序: ${processesWithSteps}/${lastValidJson.processes.length}, 总工步数: ${totalSteps}`);

                currentData = lastValidJson;
                renderProcessCards(lastValidJson, true);
                renderExcelTable(lastValidJson);
            }
        } catch (e) {
            console.log('JSON解析错误:', e.message);
        }
    }

    es.addEventListener('complete', async evt => {
        console.log('收到complete事件:', evt.data);

        // 恢复按钮状态
        btnText.style.display = 'inline';
        btnSpinner.style.display = 'none';
        submitBtn.disabled = false;

        // 根据事件内容设置状态
        if (evt.data.includes('缓存')) {
            document.getElementById('status').innerHTML = evt.data + ' <span style="color: #667eea;">⚡</span>';
        } else {
            document.getElementById('status').textContent = evt.data;
        }

        document.getElementById('update-status').style.display = 'none';
        document.getElementById('performance-info').style.display = 'none';
        es.close();

        // 检查是否是从缓存加载的
        if (evt.data.includes('缓存')) {
            console.log('✓ 数据从缓存加载，无需调用JSON接口');
            if (currentData && currentData.processes) {
                renderProcessCards(currentData, false);
                renderExcelTable(currentData);
                document.getElementById('exportExcel').style.display = 'inline-block';
                document.getElementById('exportJson').style.display = 'inline-block';
                document.getElementById('excel-title').textContent = `工艺工序分解结果 - ${currentTask}`;
            }
            return;
        }

        // 检查当前数据状态
        if (currentData && currentData.processes) {
            console.log('=== 数据完整性检查 ===');
            console.log('- 工序数量:', currentData.processes.length);
            let processesWithSteps = 0;
            let totalSteps = 0;
            let allProcessesHaveSteps = true;

            currentData.processes.forEach((p, idx) => {
                if (p.steps && p.steps.length > 0) {
                    processesWithSteps++;
                    totalSteps += p.steps.length;
                } else {
                    allProcessesHaveSteps = false;
                }
                console.log(`- 工序${idx + 1} "${p.name}": ${p.steps ? p.steps.length : 0} 个工步`);
            });

            console.log(`- 包含工步的工序: ${processesWithSteps}/${currentData.processes.length}`);
            console.log('- 总工步数:', totalSteps);
            console.log('- 所有工序都有工步:', allProcessesHaveSteps);

            // 如果数据完整（所有工序都有工步），直接使用
            if (allProcessesHaveSteps && totalSteps > 0) {
                console.log('✓ SSE数据完整，直接使用，不再调用JSON接口');
                renderProcessCards(currentData, false);
                renderExcelTable(currentData);
                document.getElementById('exportExcel').style.display = 'inline-block';
                document.getElementById('exportJson').style.display = 'inline-block';
                document.getElementById('excel-title').textContent = `工艺工序分解结果 - ${currentTask}`;
                return;
            } else {
                console.log('✗ SSE数据不完整，需要从JSON接口获取');
            }
        } else {
            console.log('✗ 没有接收到SSE数据');
        }

        // 只有数据不完整时才调用JSON接口
        console.log('调用JSON接口获取完整数据...');
        try {
            const resp = await fetch(`/api/decompose/json?task=${encodeURIComponent(currentTask)}`);
            if (!resp.ok) {
                throw new Error(`HTTP error! status: ${resp.status}`);
            }
            const data = await resp.json();
            console.log('JSON接口返回数据，工序数:', data.processes ? data.processes.length : 0);
            currentData = data;
            renderProcessCards(data, false);
            renderExcelTable(data);
            document.getElementById('exportExcel').style.display = 'inline-block';
            document.getElementById('exportJson').style.display = 'inline-block';
            document.getElementById('excel-title').textContent = `工艺工序分解结果 - ${currentTask}`;
        } catch (err) {
            console.error('获取完整 JSON 失败：', err);
            document.getElementById('status').textContent = '⚠️ 获取数据失败';
        }
    });

    es.addEventListener('error', evt => {
        console.error('SSE错误:', evt);
        document.getElementById('status').textContent = '⚠️ 出错：' + (evt.data || '连接异常');
        document.getElementById('update-status').style.display = 'none';
        document.getElementById('performance-info').style.display = 'none';

        // 恢复按钮状态
        btnText.style.display = 'inline';
        btnSpinner.style.display = 'none';
        submitBtn.disabled = false;

        es.close();
    });
});

// 导出Excel功能
function exportToExcel() {
    if (!currentData || !currentTask) return;

    const exportUrl = `/api/export/excel?task=${encodeURIComponent(currentTask)}`;

    // 检查是否支持后端Excel导出
    fetch(exportUrl)
        .then(response => {
            if (response.ok) {
                // 使用后端导出
                window.location.href = exportUrl;
            } else {
                // 降级到CSV导出
                exportToCSV();
            }
        })
        .catch(() => {
            // 出错时降级到CSV导出
            exportToCSV();
        });
}

// CSV导出备用方案
function exportToCSV() {
    if (!currentData) return;

    // 创建CSV内容
    let csv = '\uFEFF';  // UTF-8 BOM
    csv += '工序ID,工序名称,工序描述,单元,步骤ID,设备,操作\n';

    currentData.processes.forEach(proc => {
        if (proc.steps && proc.steps.length > 0) {
            proc.steps.forEach(step => {
                csv += `${proc.process_id},"${proc.name}","${proc.description || ''}","${step.unit || ''}",${step.step_id},"${step.device || ''}","${step.action || ''}"\n`;
            });
        } else {
            csv += `${proc.process_id},"${proc.name}","${proc.description || ''}","-","-","-","暂无步骤信息"\n`;
        }
    });

    // 创建Blob并下载
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', '工艺工序分解结果.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 导出JSON功能
function exportToJSON() {
    if (!currentData) return;

    // 创建带有任务信息的完整JSON
    const exportData = {
        task: currentTask,
        exportTime: new Date().toISOString(),
        processes: currentData.processes
    };

    // 格式化JSON字符串（缩进2个空格）
    const jsonString = JSON.stringify(exportData, null, 2);

    // 创建Blob并下载
    const blob = new Blob([jsonString], { type: 'application/json;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);

    // 生成文件名（包含任务名和时间戳）
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const filename = `工艺工序分解结果_${currentTask}_${timestamp}.json`;
    link.setAttribute('download', filename);

    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // 清理URL对象
    URL.revokeObjectURL(url);

    // 显示提示
    const originalText = document.getElementById('status').textContent;
    document.getElementById('status').textContent = '✓ JSON文件已下载';
    setTimeout(() => {
        document.getElementById('status').textContent = originalText;
    }, 2000);
}