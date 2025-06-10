//main.js
// 全局变量
        let allDocuments = [];
        let selectedDocIds = new Set();

        // 切换标签页
        function switchTab(tabName, event) {
            // 移除所有active类
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

            // 添加active类到被点击的标签
            if (event && event.target) {
                event.target.classList.add('active');
            } else {
                // 如果没有event，通过tabName查找对应的标签
                document.querySelectorAll('.tab').forEach(tab => {
                    if (tab.textContent === getTabLabel(tabName)) {
                        tab.classList.add('active');
                    }
                });
            }

            // 显示对应的内容
            document.getElementById(tabName + 'Tab').classList.add('active');
        }

        // 获取标签标题的辅助函数
        function getTabLabel(tabName) {
            const labels = {
                'text': '文本',
                'url': 'URL',
                'file': '文件'
            };
            return labels[tabName] || tabName;
        }

        // 显示提示信息
        function showAlert(message, type = 'success') {
            const alert = document.getElementById(type + 'Alert');
            const messageEl = document.getElementById(type + 'Message');
            messageEl.textContent = message;
            alert.classList.add('show');
            setTimeout(() => alert.classList.remove('show'), 5000);
        }

        // 更新查询范围
        function updateQueryScope() {
            const scope = document.getElementById('queryScope').value;
            document.getElementById('domainSelect').style.display = scope === 'domain' ? 'block' : 'none';
            document.getElementById('docsSelect').style.display = scope === 'docs' ? 'block' : 'none';
        }

        // 更新深度标签
        function updateDepthLabel(value) {
            document.getElementById('depthLabel').textContent = `深度: ${value}`;
        }

        // 加载文档列表
        async function loadDocuments() {
            try {
                const response = await fetch('/api/documents');
                const data = await response.json();
                allDocuments = data;
                renderDocuments();
                renderDocumentsList();
                loadDomains();
                loadStats();
            } catch (error) {
                console.error('加载文档失败:', error);
                showAlert('加载文档失败: ' + error.message, 'error');
            }
        }

        // 加载领域列表
        async function loadDomains() {
            try {
                const response = await fetch('/api/domains');
                const domains = await response.json();
                const select = document.getElementById('domainFilter');
                select.innerHTML = '<option value="">请选择领域</option>';
                domains.forEach(domain => {
                    select.innerHTML += `<option value="${domain}">${domain}</option>`;
                });
            } catch (error) {
                console.error('加载领域失败:', error);
            }
        }

        // 加载统计信息
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                const statsGrid = document.getElementById('statsGrid');

                statsGrid.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_docs}</div>
                        <div class="stat-label">文档总数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_domains}</div>
                        <div class="stat-label">领域数量</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_words.toLocaleString()}</div>
                        <div class="stat-label">总词数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_tokens.toLocaleString()}</div>
                        <div class="stat-label">总Token数</div>
                    </div>
                `;
            } catch (error) {
                console.error('加载统计信息失败:', error);
            }
        }

        // 渲染文档列表（用于查询）
        function renderDocuments() {
            const docsList = document.getElementById('docsList');
            docsList.innerHTML = allDocuments.map(doc => `
                <div class="document-item ${selectedDocIds.has(doc.doc_id) ? 'selected' : ''}" 
                     onclick="toggleDocSelection('${doc.doc_id}')">
                    <div class="document-title">${doc.title}</div>
                    <div class="document-meta">
                        <span class="domain-tag">${doc.domain}</span>
                        <span class="meta-item">版本: ${doc.version}</span>
                        <span class="meta-item">${doc.word_count.toLocaleString()} 词</span>
                    </div>
                </div>
            `).join('');
        }

        // 渲染文档列表（用于管理）
        function renderDocumentsList() {
            const documentsList = document.getElementById('documentsList');
            documentsList.innerHTML = allDocuments.map(doc => `
                <div class="document-item">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div style="flex: 1;">
                            <div class="document-title">${doc.title}</div>
                            <div class="document-meta">
                                <span class="domain-tag">${doc.domain}</span>
                                <span class="meta-item">ID: ${doc.doc_id}</span>
                                <span class="meta-item">版本: ${doc.version}</span>
                                <span class="meta-item">${doc.word_count.toLocaleString()} 词</span>
                                <span class="meta-item">创建于: ${new Date(doc.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                        <button class="btn btn-danger" onclick="deleteDocument('${doc.doc_id}', '${doc.title}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                            删除
                        </button>
                    </div>
                </div>
            `).join('');
        }

        // 切换文档选择
        function toggleDocSelection(docId) {
            if (selectedDocIds.has(docId)) {
                selectedDocIds.delete(docId);
            } else {
                selectedDocIds.add(docId);
            }
            renderDocuments();
        }

        // 过滤文档
        function filterDocuments() {
            const searchTerm = document.getElementById('searchDocs').value.toLowerCase();
            const filtered = allDocuments.filter(doc =>
                doc.title.toLowerCase().includes(searchTerm) ||
                doc.domain.toLowerCase().includes(searchTerm)
            );

            const documentsList = document.getElementById('documentsList');
            documentsList.innerHTML = filtered.map(doc => `
                <div class="document-item">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div style="flex: 1;">
                            <div class="document-title">${doc.title}</div>
                            <div class="document-meta">
                                <span class="domain-tag">${doc.domain}</span>
                                <span class="meta-item">ID: ${doc.doc_id}</span>
                                <span class="meta-item">版本: ${doc.version}</span>
                                <span class="meta-item">${doc.word_count.toLocaleString()} 词</span>
                                <span class="meta-item">创建于: ${new Date(doc.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                        <button class="btn btn-danger" onclick="deleteDocument('${doc.doc_id}', '${doc.title}')">
                            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                            删除
                        </button>
                    </div>
                </div>
            `).join('');
        }

        // 删除文档
        async function deleteDocument(docId, title) {
            if (!confirm(`确定要删除文档 "${title}" 吗？`)) return;

            try {
                const response = await fetch('/api/document', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ doc_id: docId })
                });

                if (response.ok) {
                    showAlert('文档删除成功');
                    loadDocuments();
                } else {
                    const error = await response.json();
                    showAlert('删除失败: ' + error.detail, 'error');
                }
            } catch (error) {
                showAlert('删除失败: ' + error.message, 'error');
            }
        }

        // 处理文本表单提交
        document.getElementById('textForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            if (!formData.get("max_pages")) {
                formData.delete("max_pages");
            }
            const data = Object.fromEntries(formData);

            document.getElementById('addLoading').classList.add('active');

            try {
                const response = await fetch('/api/document/text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    const result = await response.json();
                    showAlert(`文档添加成功！ID: ${result.doc_id}`);
                    e.target.reset();
                    loadDocuments();
                } else {
                    const error = await response.json();
                    showAlert('添加失败: ' + error.detail, 'error');
                }
            } catch (error) {
                showAlert('添加失败: ' + error.message, 'error');
            } finally {
                document.getElementById('addLoading').classList.remove('active');
            }
        });

        // 处理URL表单提交
        document.getElementById('urlForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);

            if (data.max_pages) {
                data.max_pages = parseInt(data.max_pages);
            } else {
                delete data.max_pages;
            }

            document.getElementById('addLoading').classList.add('active');

            try {
                const response = await fetch('/api/document/url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    const result = await response.json();
                    showAlert(`文档添加成功！ID: ${result.doc_id}`);
                    e.target.reset();
                    loadDocuments();
                } else {
                    const error = await response.json();
                    showAlert('添加失败: ' + error.detail, 'error');
                }
            } catch (error) {
                showAlert('添加失败: ' + error.message, 'error');
            } finally {
                document.getElementById('addLoading').classList.remove('active');
            }
        });

        // 处理文件表单提交
            document.getElementById('fileForm').addEventListener('submit', async (e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
                // 删除空的 max_pages，避免空字符串转 int 报错
              if (!formData.get('max_pages')) {
                formData.delete('max_pages');
              }

              document.getElementById('addLoading').classList.add('active');

              try {
                const response = await fetch('/api/document/file', {
                  method: 'POST',
                  body: formData
                });

                if (response.ok) {
                  const result = await response.json();
                  showAlert(`文档添加成功！ID: ${result.doc_id}`);
                  e.target.reset();
                  await loadDocuments();
                } else {
                  const error = await response.json();
                  console.error("上传失败——HTTP", response.status, error);
                  showAlert('添加失败: ' + JSON.stringify(error), 'error');
                }
              } catch (error) {
                showAlert('添加失败: ' + error.message, 'error');
              } finally {
                document.getElementById('addLoading').classList.remove('active');
              }
            });

        // 处理查询表单提交
        document.getElementById('queryForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const scope = formData.get('scope');

            const queryData = {
                question: formData.get('question'),
                max_depth: parseInt(formData.get('max_depth'))
            };

            if (scope === 'domain' && formData.get('domain')) {
                queryData.domain = formData.get('domain');
            } else if (scope === 'docs' && selectedDocIds.size > 0) {
                queryData.doc_ids = Array.from(selectedDocIds);
            }

            document.getElementById('queryLoading').classList.add('active');
            document.getElementById('queryResult').style.display = 'none';

            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(queryData)
                });

                if (response.ok) {
                    const result = await response.json();
                    displayQueryResult(result);
                } else {
                    const error = await response.json();
                    showAlert('查询失败: ' + error.detail, 'error');
                }
            } catch (error) {
                showAlert('查询失败: ' + error.message, 'error');
            } finally {
                document.getElementById('queryLoading').classList.remove('active');
            }
        });

        // 显示查询结果
        function displayQueryResult(result) {
            const resultDiv = document.getElementById('queryResult');

            let html = '<div class="query-result">';
            html += `<div class="answer-text">${result.answer.replace(/\n/g, '<br>')}</div>`;
            html += '<div style="display: flex; align-items: center; gap: 10px;">';
            html += `<span class="confidence ${result.confidence}">${result.confidence.toUpperCase()} 置信度</span>`;

            if (result.citations && result.citations.length > 0) {
                html += `<div class="citations">引用: ${result.citations.join(', ')}</div>`;
            }
            html += '</div>';

            if (result.paragraphs && result.paragraphs.length > 0) {
                html += '<details style="margin-top: 20px;">';
                html += '<summary style="cursor: pointer; font-weight: 600;">查看引用段落</summary>';
                html += '<div style="margin-top: 10px;">';
                result.paragraphs.slice(0, 3).forEach((para, idx) => {
                    html += `
                        <div style="background: white; padding: 15px; margin-top: 10px; border-radius: 10px; border-left: 3px solid #667eea;">
                            <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">
                                段落 ${para.display_id || para.id} - 来源: ${para.doc_title || '未知文档'}
                            </div>
                            <div style="color: #333;">
                                ${para.text.substring(0, 300)}${para.text.length > 300 ? '...' : ''}
                            </div>
                        </div>
                    `;
                });
                html += '</div></details>';
            }

            html += '</div>';

            resultDiv.innerHTML = html;
            resultDiv.style.display = 'block';
        }

        // 页面加载时初始化
        document.addEventListener('DOMContentLoaded', () => {
            loadDocuments();
        });