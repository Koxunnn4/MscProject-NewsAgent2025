/* Copied from MscProject-NewsAgent2025-chenjingyin/static/app.js */
// ===== 全局变量 =====
let currentAnalysisData = null;
let currentPage = 1;
const PAGE_SIZE = 50;

// ===== 页面初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    // Only run analyzer-specific scripts if on the analyzer page
    if (document.getElementById('analyze-btn')) {
        setupEventListeners();
        setupChannelToggle();
        loadChannels();
        
        // 初始化 UI 标签
        const sourceSelect = document.getElementById('data-source');
        if (sourceSelect) {
            updateUILabels(sourceSelect.value);
        }
    }
});

// ===== UI 更新 =====
function updateUILabels(source) {
    const tabBtn = document.getElementById('tab-currencies-btn');
    const statTitle = document.getElementById('stat-currency-title');
    const tableHeader = document.getElementById('table-header-currency');

    if (source === 'hkstocks') {
        if (tabBtn) tabBtn.textContent = '行业统计';
        if (statTitle) statTitle.textContent = '🏭 行业种类';
        if (tableHeader) tableHeader.textContent = '行业';
    } else {
        if (tabBtn) tabBtn.textContent = '币种统计';
        if (statTitle) statTitle.textContent = '💰 币种种类';
        if (tableHeader) tableHeader.textContent = '币种';
    }
}

// ===== 事件监听 =====
function setupEventListeners() {
    // 分析按钮
    document.getElementById('analyze-btn').addEventListener('click', performAnalysis);

    const sourceSelect = document.getElementById('data-source');
    if (sourceSelect) {
        sourceSelect.addEventListener('change', () => {
            loadChannels();
            updateUILabels(sourceSelect.value);
        });
    }

    // 标签页切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', switchTab);
    });

    // 查询按钮
    document.getElementById('query-btn').addEventListener('click', performQuery);

    // 回车键查询
    document.getElementById('query-keyword').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performQuery();
        }
    });

    // 分页按钮
    const prevBtn = document.getElementById('keywords-prev');
    const nextBtn = document.getElementById('keywords-next');
    if (prevBtn) prevBtn.addEventListener('click', () => prevPage());
    if (nextBtn) nextBtn.addEventListener('click', () => nextPage());
}

// ===== 加载频道列表（默认全选） =====
async function loadChannels() {
    try {
        const source = getSelectedSource();
        const response = await fetch(`/api/channels?source=${source}`);
        const data = await response.json();

        const container = document.getElementById('channels-container');
        container.innerHTML = '';

        if (data.supports_channels && data.channels && data.channels.length) {
            data.channels.forEach(channel => {
                const checkbox = document.createElement('div');
                checkbox.className = 'checkbox-item';
                checkbox.innerHTML = `
                    <input type="checkbox" id="channel-${channel.id}" value="${channel.channel_id}" checked>
                    <label for="channel-${channel.id}">${channel.name}</label>
                `;
                container.appendChild(checkbox);
            });
        } else {
            const hint = document.createElement('p');
            hint.textContent = '该数据源无需频道筛选';
            hint.className = 'channels-hint';
            container.appendChild(hint);
        }

        toggleChannelSectionVisibility(Boolean(data.supports_channels));
    } catch (error) {
        console.error('加载频道失败:', error);
    }
}

function toggleChannelSectionVisibility(enabled) {
    const wrapper = document.querySelector('.channels-collapse-wrapper');
    const toggleBtn = document.getElementById('channels-toggle');
    const collapseContent = document.getElementById('channels-collapse-content');

    if (!wrapper || !toggleBtn || !collapseContent) return;

    wrapper.style.opacity = enabled ? '1' : '0.6';
    toggleBtn.disabled = !enabled;
    toggleBtn.style.visibility = enabled ? 'visible' : 'hidden';
    collapseContent.style.display = 'block';
}

// ===== 设置频道列表折叠功能 =====
function setupChannelToggle() {
    const toggleBtn = document.getElementById('channels-toggle');
    const collapseContent = document.getElementById('channels-collapse-content');

    if (!toggleBtn || !collapseContent) {
        console.warn('频道折叠元素未找到');
        return;
    }

    // 默认展开（用户可见）
    collapseContent.style.display = 'block';

    toggleBtn.addEventListener('click', (e) => {
        e.preventDefault();

        const isHidden = collapseContent.style.display === 'none';
        collapseContent.style.display = isHidden ? 'block' : 'none';

        // 更新图标
        const icon = toggleBtn.querySelector('.toggle-icon');
        if (icon) {
            icon.textContent = isHidden ? '▼' : '▲';
        }
    });
}

// ===== 执行分析 =====
async function performAnalysis() {
    const loading = document.getElementById('loading');
    const analyzeBtn = document.getElementById('analyze-btn');

    try {
        // 获取筛选参数
        const timeRange = getTimeRange();
        const channelIds = getSelectedChannels();
        const source = getSelectedSource();

        // 显示加载状态
        loading.style.display = 'flex';
        analyzeBtn.disabled = true;

        // 调用 API
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                time_range: timeRange,
                channel_ids: channelIds,
                data_source: source
            })
        });

        const data = await response.json();

        if (data.success) {
            currentAnalysisData = data;
            currentPage = 1;  // 重置分页
            displayResults(data);
            document.getElementById('results-panel').style.display = 'block';
        } else {
            alert('分析失败: ' + data.error);
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    } finally {
        loading.style.display = 'none';
        analyzeBtn.disabled = false;
    }
}// ===== 获取时间范围 =====
function getTimeRange() {
    const timeRangeSelect = document.getElementById('time-range').value;

    if (!timeRangeSelect) {
        return null;
    }

    const minutes = parseInt(timeRangeSelect);
    const now = new Date();
    const start = new Date(now.getTime() - minutes * 60000);

    return [start.toISOString(), now.toISOString()];
}

// ===== 获取选中的频道 =====
function getSelectedChannels() {
    const checkboxes = document.querySelectorAll('#channels-container input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

function getSelectedSource() {
    const select = document.getElementById('data-source');
    return select ? select.value : 'crypto';
}

// ===== 显示结果 =====
function displayResults(data) {
    // 更新统计卡片
    document.getElementById('total-rows').textContent = data.total_rows.toLocaleString();
    document.getElementById('keyword-total').textContent = data.keyword_total;
    document.getElementById('currency-total').textContent = data.currency_total;

    // 显示关键词表格（第一页）
    displayKeywordPage();

    // 清空币种表格
    document.getElementById('currencies-tbody').innerHTML = '';

    // 填充币种表格
    data.currency_stats.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${escapeHtml(item.word)}</strong></td>
            <td>${item.count}</td>
            <td>${item.ratio.toFixed(2)}%</td>
        `;
        document.getElementById('currencies-tbody').appendChild(row);
    });

    // 渲染趋势图
    if (data.trend_data) {
        renderTrendChart(data.trend_data);
    }

    // 显示关键词标签页
    switchTabToElement('keywords');
}

// ===== 分页功能 =====
function displayKeywordPage() {
    if (!currentAnalysisData) return;

    const tbody = document.getElementById('keywords-tbody');
    tbody.innerHTML = '';

    const allKeywords = currentAnalysisData.keyword_stats;
    const totalPages = Math.ceil(allKeywords.length / PAGE_SIZE);

    // 验证页码
    if (currentPage < 1) currentPage = 1;
    if (currentPage > totalPages) currentPage = totalPages;

    // 计算起始和结束索引
    const startIdx = (currentPage - 1) * PAGE_SIZE;
    const endIdx = Math.min(startIdx + PAGE_SIZE, allKeywords.length);

    // 显示当前页的数据
    for (let i = startIdx; i < endIdx; i++) {
        const item = allKeywords[i];
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${i + 1}</td>
            <td><strong>${escapeHtml(item.word)}</strong></td>
            <td>${item.count}</td>
            <td>${item.ratio.toFixed(2)}%</td>
        `;
        tbody.appendChild(row);
    }

    // 更新分页信息
    const pageInfo = document.getElementById('keywords-page-info');
    if (pageInfo) {
        pageInfo.textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页 (总计 ${allKeywords.length} 条)`;
    }

    // 更新按钮状态
    const prevBtn = document.getElementById('keywords-prev');
    const nextBtn = document.getElementById('keywords-next');
    if (prevBtn) prevBtn.disabled = currentPage === 1;
    if (nextBtn) nextBtn.disabled = currentPage === totalPages;
}

function prevPage() {
    currentPage--;
    displayKeywordPage();
}

function nextPage() {
    if (currentAnalysisData) {
        const totalPages = Math.ceil(currentAnalysisData.keyword_stats.length / PAGE_SIZE);
        if (currentPage < totalPages) {
            currentPage++;
            displayKeywordPage();
        }
    }
}// ===== 标签页切换 =====
function switchTab(event) {
    const tabName = event.target.dataset.tab;
    switchTabToElement(tabName);
}

function switchTabToElement(tabName) {
    // 隐藏所有标签页
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // 移除所有按钮的 active 类
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // 显示选中标签页
    const tabElement = document.getElementById(`${tabName}-tab`);
    if (tabElement) {
        tabElement.classList.add('active');
    }

    // 激活对应按钮
    const btnElement = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
    if (btnElement) {
        btnElement.classList.add('active');
    }

    // 如果切换到可视化标签页，且有数据，则渲染词云
    if (tabName === 'visualization' && currentAnalysisData) {
        // Small delay to ensure DOM is updated and container has size
        setTimeout(() => {
            renderWordCloud(currentAnalysisData);
        }, 50);
    }
}

// ===== 趋势图渲染 =====
let trendChart = null;

function renderTrendChart(trendData) {
    const ctx = document.getElementById('trend-chart');
    if (!ctx) return;

    if (trendChart) {
        trendChart.destroy();
    }

    // trendData structure: { labels: [...], datasets: [{label: 'keyword', data: [...]}, ...] }
    
    // Generate colors for datasets - Optimized for distinction
    const colors = [
        '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#00FFFF', '#FF00FF', // Basic brights
        '#800000', '#008000', '#000080', '#808000', '#008080', '#800080', // Darker versions
        '#FF4500', '#32CD32', '#1E90FF', '#FFD700', '#00CED1', '#FF1493', // Distinct shades
        '#8B4513', '#2E8B57', '#4682B4', '#DAA520', '#20B2AA', '#C71585', // Earthy/Muted
        '#DC143C', '#7FFF00', '#4169E1', '#F0E68C', '#AFEEEE', '#DB7093'  // Others
    ];

    // Helper to convert hex to rgba
    function hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    const datasets = trendData.datasets.map((ds, index) => {
        const color = colors[index % colors.length];
        return {
            label: ds.label,
            data: ds.data,
            borderColor: hexToRgba(color, 0.6), // Increased default opacity (was 0.3)
            backgroundColor: hexToRgba(color, 0.6),
            borderWidth: 2, // Increased default width (was 1)
            tension: 0.4,
            pointRadius: 0, 
            pointHoverRadius: 6, // Show a dot when hovering for better feedback
            pointHitRadius: 60, // Significantly increased hit area for easier selection
            fill: false,
            originalColor: color 
        };
    });

    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendData.labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'nearest',
                axis: 'xy',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false 
                },
                tooltip: {
                    enabled: true,
                    mode: 'nearest',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + context.parsed.y;
                        }
                    },
                    filter: function(tooltipItem) {
                        // Only show tooltip for the highlighted dataset
                        // We check if borderWidth is > 2 (our highlight condition)
                        return tooltipItem.dataset.borderWidth > 2;
                    }
                },
                title: {
                    display: true,
                    text: 'Top 30 关键词趋势 (鼠标悬停高亮显示)'
                }
            },
            onHover: function(e, activeElements, chart) {
                let hasActive = activeElements.length > 0;
                
                chart.data.datasets.forEach((dataset, i) => {
                    if (hasActive && activeElements[0].datasetIndex === i) {
                        // Highlight active
                        dataset.borderColor = hexToRgba(dataset.originalColor, 1.0);
                        dataset.borderWidth = 4; // Thicker highlight
                        dataset.order = -1; // Bring to front
                    } else {
                        // Dim others - Increased opacity (was 0.1/0.3)
                        dataset.borderColor = hexToRgba(dataset.originalColor, hasActive ? 0.2 : 0.6);
                        dataset.borderWidth = 1; // Thinner when not selected
                        dataset.order = 0;
                    }
                });
                
                chart.update('none'); 
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '时间'
                    },
                    ticks: {
                        maxTicksLimit: 10
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '频次'
                    },
                    beginAtZero: true
                }
            }
        }
    });
}

// ===== 执行关键词查询 =====
async function performQuery() {
    const keyword = document.getElementById('query-keyword').value.trim();
    const source = getSelectedSource();

    if (!keyword) {
        alert('请输入关键词');
        return;
    }

    // No longer need to check for currentAnalysisData, as data is fetched on demand
    // if (!currentAnalysisData) {
    //     alert('请先执行分析');
    //     return;
    // }

    try {
        const response = await fetch('/api/query-keyword', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                keyword: keyword,
                channel_ids: getSelectedChannels(),
                time_range: getTimeRange(),
                data_source: source
            })
        });

        const data = await response.json();

        if (data.success) {
            displayQueryResult(data);
            switchTabToElement('query');
        } else {
            alert('查询失败: ' + data.error);
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
        console.error('查询错误:', error);
    }
}// ===== 显示查询结果 =====
function displayQueryResult(data) {
    const resultDiv = document.getElementById('query-result');
    const statusDiv = document.getElementById('query-status');
    const similarDiv = document.getElementById('query-similar');

    // 显示存在状态
    if (data.exists) {
        statusDiv.className = 'exists';
        statusDiv.innerHTML = `✓ 关键词 "<strong>${escapeHtml(data.keyword)}</strong>" 在数据库中存在`;
    } else {
        statusDiv.className = 'not-exists';
        statusDiv.innerHTML = `✗ 关键词 "<strong>${escapeHtml(data.keyword)}</strong>" 在数据库中不存在`;
    }

    // 清空相似词列表
    similarDiv.innerHTML = '';

    if (data.similar_words.length > 0) {
        const title = document.createElement('h4');
        title.textContent = '与您的查询最接近的Top 10关键词：';
        title.style.marginBottom = '15px';
        similarDiv.appendChild(title);

        // 填充相似词
        data.similar_words.forEach((item, index) => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'similar-word-item';
            itemDiv.innerHTML = `
                <div class="similar-word-info">
                    <div class="similar-word-name">${index + 1}. ${escapeHtml(item.word)}</div>
                    <div class="similar-word-count">出现次数: ${item.count}</div>
                </div>
                <div class="similar-word-score">${(item.similarity * 100).toFixed(2)}%</div>
            `;
            similarDiv.appendChild(itemDiv);
        });
    } else {
        const noResultDiv = document.createElement('p');
        noResultDiv.textContent = '未找到相似的关键词（可能是因为关键词频率过低或没有有效向量）';
        noResultDiv.style.color = '#718096';
        noResultDiv.style.fontStyle = 'italic';
        similarDiv.appendChild(noResultDiv);
    }

    resultDiv.style.display = 'block';
}

// ===== 工具函数 =====
function escapeHtml(text) {
    if (typeof text !== 'string') return text;
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ===== 导出 CSV 功能 =====
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const rows = table.querySelectorAll('tr');
    const csv = [];

    for (let i = 0; i < rows.length; i++) {
        const row = [], cols = rows[i].querySelectorAll('td, th');
        for (let j = 0; j < cols.length; j++) {
            // Clean text content: remove newlines and escape quotes
            let data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/(\s\s)/gm, ' ');
            data = data.replace(/"/g, '""');
            row.push('"' + data + '"');
        }
        csv.push(row.join(','));
    }

    const csvFile = new Blob([csv.join('\n')], { type: 'text/csv' });
    const downloadLink = document.createElement('a');
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

// ===== 词云渲染 =====
function renderWordCloud(data) {
    const canvas = document.getElementById('word-cloud-canvas');
    // Support both keyword_stats (from backend) and keywords (legacy/generic)
    const keywords = data.keyword_stats || data.keywords;
    
    if (!canvas || !data || !keywords) return;

    // Prepare data for wordcloud2.js: [[word, weight], ...]
    // Use count as weight. Normalize if needed, but library handles it well.
    // Take top 100 keywords for clarity
    const list = keywords.slice(0, 100).map(item => [item.word, item.count]);

    if (list.length === 0) {
        canvas.innerHTML = '<p style="text-align:center; padding-top: 100px; color: #999;">暂无数据生成词云</p>';
        return;
    }

    // Clear previous content if it was text
    canvas.innerHTML = '';
    
    // Ensure canvas has dimensions
    if (canvas.offsetWidth === 0 || canvas.offsetHeight === 0) {
        // If hidden, we can't render properly. 
        // It will be rendered when tab switches.
        return;
    }

    WordCloud(canvas, {
        list: list,
        gridSize: 16,
        weightFactor: function (size) {
            // Dynamic scaling based on max count
            const max = list[0][1];
            return (size / max) * 60 + 10; // Min 10px, Max 70px
        },
        fontFamily: 'system-ui, -apple-system, sans-serif',
        color: function (word, weight) {
            // Random colors from our palette
            const colors = ['#2563EB', '#7C3AED', '#10B981', '#F59E0B', '#EF4444', '#6B7280'];
            return colors[Math.floor(Math.random() * colors.length)];
        },
        rotateRatio: 0.5,
        rotationSteps: 2,
        backgroundColor: '#ffffff',
        drawOutOfBound: false
    });
}

// ===== 添加样式表中缺少的相似度条样式 =====
const style = document.createElement('style');
style.textContent = `
    .similarity-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        position: relative;
    }

    .similarity-fill {
        height: 6px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 3px;
        transition: width 0.3s;
        flex: 0 0 150px;
    }

    .similarity-bar span {
        font-weight: 600;
        color: var(--primary-color);
        min-width: 50px;
    }
`;
document.head.appendChild(style);
