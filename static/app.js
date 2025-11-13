// ===== 全局变量 =====
let currentAnalysisData = null;
let currentPage = 1;
const PAGE_SIZE = 50;

// ===== 页面初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    loadChannels();
    setupEventListeners();
    setupChannelToggle();
});

// ===== 事件监听 =====
function setupEventListeners() {
    // 分析按钮
    document.getElementById('analyze-btn').addEventListener('click', performAnalysis);

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
        const response = await fetch('/api/channels');
        const data = await response.json();

        const container = document.getElementById('channels-container');
        container.innerHTML = '';

        data.channels.forEach(channel => {
            const checkbox = document.createElement('div');
            checkbox.className = 'checkbox-item';
            checkbox.innerHTML = `
                <input type="checkbox" id="channel-${channel.id}" value="${channel.channel_id}" checked>
                <label for="channel-${channel.id}">${channel.name}</label>
            `;
            container.appendChild(checkbox);
        });
    } catch (error) {
        console.error('加载频道失败:', error);
    }
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

        // 显示加载状态
        loading.style.display = 'flex';
        analyzeBtn.disabled = true;

        // 调用 API
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                time_range: timeRange,
                channel_ids: channelIds
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
            <td>${item.occur_count}</td>
            <td>${item.ratio.toFixed(2)}%</td>
        `;
        document.getElementById('currencies-tbody').appendChild(row);
    });

    // 清空相似度表格
    document.getElementById('similarity-tbody').innerHTML = '';

    // 填充相似度表格
    if (data.similarity_results && data.similarity_results.length > 0) {
        data.similarity_results.forEach((item, index) => {
            const row = document.createElement('tr');
            const similarity = (item.similarity * 100).toFixed(2);
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${escapeHtml(item.word1)}</td>
                <td>${item.count1}</td>
                <td>${escapeHtml(item.word2)}</td>
                <td>${item.count2}</td>
                <td><span class="similarity-score">${similarity}%</span></td>
            `;
            document.getElementById('similarity-tbody').appendChild(row);
        });
    } else {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="6" style="text-align: center; color: #718096;">暂无相似度数据（可能是关键词数不足或模型加载失败）</td>';
        document.getElementById('similarity-tbody').appendChild(row);
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
            <td>${item.occur_count}</td>
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
}

// ===== 执行关键词查询 =====
async function performQuery() {
    const keyword = document.getElementById('query-keyword').value.trim();

    if (!keyword) {
        alert('请输入关键词');
        return;
    }

    if (!currentAnalysisData) {
        alert('请先执行分析');
        return;
    }

    try {
        const response = await fetch('/api/query-keyword', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                keyword: keyword,
                channel_ids: getSelectedChannels(),
                time_range: getTimeRange()
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
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
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
