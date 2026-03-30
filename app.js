import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.1/firebase-app.js";
import { getDatabase, ref, onValue } from "https://www.gstatic.com/firebasejs/10.8.1/firebase-database.js";

const firebaseConfig = {
    databaseURL: "https://wanakachi-monitoring-default-rtdb.asia-southeast1.firebasedatabase.app/"
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

const chartKeyboard = echarts.init(document.getElementById('chart-keyboard'));
const chartMouse = echarts.init(document.getElementById('chart-mouse'));
const chartGaugeMouse = echarts.init(document.getElementById('chart-gauge-mouse'));
const chartGaugeScroll = echarts.init(document.getElementById('chart-gauge-scroll'));

const state = { app: null, music: null, input: null, odometer: null };
const OFFLINE_THRESHOLD_SECONDS = 120; 

// 1. 数据拉取
onValue(ref(db, 'now_playing'), (snapshot) => { state.app = snapshot.val(); });
onValue(ref(db, 'music_status'), (snapshot) => { state.music = snapshot.val(); });
onValue(ref(db, 'input_history'), (snapshot) => {
    const payload = snapshot.val();
    if (!payload) return;
    state.input = payload.last_updated;
    if (payload.data) renderCharts(payload.data);
    if (payload.odometer) state.odometer = payload.odometer; 
});

// 2. 仪表盘样式配置
const getGaugeOption = (chartName, unitStr, colorMain, maxValue, dataValue) => ({
    series: [{
        name: chartName,
        type: 'gauge',
        center: ['50%', '65%'], 
        radius: '75%', 
        startAngle: 180, 
        endAngle: 0,
        min: 0,
        max: maxValue,
        splitNumber: 5,
        axisLine: {
            lineStyle: {
                width: 10,
                color: [
                    [1, new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: colorMain + '20' }, 
                        { offset: 0.5, color: colorMain }, 
                        { offset: 1, color: colorMain + '20' }
                    ])]
                ]
            }
        },
        axisTick: { 
            distance: -15, 
            length: 8, 
            lineStyle: { color: colorMain + '50', width: 2 } 
        },
        splitLine: { 
            distance: -18, 
            length: 12, 
            lineStyle: { color: colorMain, width: 3 } 
        },
        axisLabel: { 
            distance: -30, 
            color: '#8b8b99', 
            fontSize: 11,
            formatter: function (value) {
                if (value === 0) return '0';
                if (value === maxValue) return maxValue;
                return value;
            }
        },
        pointer: { 
            icon: 'triangle', 
            length: '80%',
            width: 8,
            itemStyle: { color: colorMain, borderJoin: 'round' }
        },
        detail: { 
            valueAnimation: true,
            formatter: `{value|{value}} {unit|${unitStr}}`,
            rich: {
                value: { fontSize: 32, fontWeight: 'bolder', color: '#fff', padding: [10, 0] },
                unit: { fontSize: 14, color: '#8b8b99', verticalAlign: 'bottom' }
            },
            offsetCenter: [0, '55%'] 
        },
        data: [{ value: dataValue }]
    }]
});

// 3. ECharts 柱状图配置
function renderCharts(chartData) {
    const boundaries = chartData.map(item => item.time);
    const lastTime = boundaries[boundaries.length - 1];
    let lastHour = parseInt(lastTime.split(':')[0], 10);
    let nextHour = (lastHour + 1) % 24;
    boundaries.push(nextHour.toString().padStart(2, '0') + ':00'); 

    const dummyData = chartData.map((_, i) => i);
    const presses = chartData.map(item => item.presses);
    const clicks = chartData.map(item => item.clicks);

    chartKeyboard.setOption(getChartOptionBar('敲击次数', '#e056fd', boundaries, dummyData, presses));
    chartMouse.setOption(getChartOptionBar('点击次数', '#00d2ff', boundaries, dummyData, clicks));
}

const getChartOptionBar = (name, colorStr, boundaries, dummyData, dataY) => ({
    tooltip: { trigger: 'axis', backgroundColor: '#1e1e2f', textStyle: { color: '#fff' }, borderColor: 'rgba(255,255,255,0.1)', formatter: function(params) {
        const item = params[0];
        return `<div style="font-size: 12px; color: #8b8b99; margin-bottom: 6px;">🕒 ${boundaries[item.dataIndex]} ~ ${boundaries[item.dataIndex + 1]}</div>
                <div>${item.marker} <span style="color: #fff;">${item.seriesName}:</span> <span style="font-weight: bold; font-size: 16px; color: ${colorStr}; margin-left: 8px;">${item.value}</span></div>`;
    }},
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: [
        { type: 'category', boundaryGap: false, data: boundaries, axisLabel: { color: '#8b8b99', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: true, length: 5, lineStyle: { color: '#2c2c3f' } }, axisPointer: { type: 'none' } },
        { type: 'category', boundaryGap: true, data: dummyData, show: false, axisPointer: { show: true, type: 'line', lineStyle: { color: '#555566', type: 'dashed', width: 1 } } }
    ],
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#2c2c3f', type: 'dashed' } }, axisLabel: { color: '#8b8b99' } },
    series: [{ name: name, type: 'bar', xAxisIndex: 1, barCategoryGap: '2%', itemStyle: { borderRadius: [4, 4, 0, 0], color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: colorStr }, { offset: 1, color: colorStr + '10' }]) }, data: dataY }]
});

// 4. 卡片 DOM 渲染
function renderApp(isOffline, diffSeconds) {
    if (!state.app) return;
    const card = document.getElementById('card-app');
    const dot = document.getElementById('app-dot');
    const statusText = document.getElementById('app-status-text');
    const appName = document.getElementById('app-name');
    const categoryContainer = document.getElementById('app-category-container');
    const categoryBadge = document.getElementById('app-category');
    const durationEl = document.getElementById('app-duration');

    let displayApp = state.app.app;
    let displayCat = null;
    if (state.app.status === 'active') {
        const match = state.app.app.match(/(.+) \[(.+)\]/);
        if (match) { displayApp = match[1]; displayCat = match[2]; }
    } else { displayApp = 'System Standby'; }

    appName.innerText = displayApp;
    if (displayCat) { categoryBadge.innerText = displayCat; categoryContainer.style.display = 'block'; } 
    else { categoryContainer.style.display = 'none'; }
    document.getElementById('time-app').innerText = formatRelativeTime(state.app.last_updated);

    if (isOffline) {
        card.className = 'card offline-mode';
        dot.className = 'status-dot';
        statusText.innerText = '监控已断开 / Offline';
        durationEl.innerText = state.app.status === 'active' ? formatDuration(state.app.duration_seconds) + ' (数据已冻结)' : '';
    } else {
        if (state.app.status === 'active') {
            card.className = 'card';
            dot.className = 'status-dot active';
            statusText.innerText = '当前正在使用';
            durationEl.innerText = formatDuration(state.app.duration_seconds + diffSeconds);
        } else {
            card.className = 'card afk-mode';
            dot.className = 'status-dot afk';
            statusText.innerText = '当前离开 / 挂机';
            durationEl.innerText = '';
        }
    }
}

function renderMusic(isOffline) {
    if (!state.music) return;
    const card = document.getElementById('card-music');
    const dot = document.getElementById('music-dot');
    const headerText = document.getElementById('music-header-text');
    const titleEl = document.getElementById('music-title');
    const artistEl = document.getElementById('music-artist');

    titleEl.innerText = state.music.title === '' ? '休眠中' : state.music.title;
    artistEl.innerText = state.music.artist === '未知歌手' ? '' : state.music.artist;
    document.getElementById('time-music').innerText = formatRelativeTime(state.music.last_updated);

    if (isOffline) {
        card.className = 'card offline-mode';
        dot.className = 'status-dot';
        headerText.innerText = 'Offline';
    } else {
        card.className = 'card';
        if (state.music.status === 'playing') {
            dot.className = 'status-dot playing';
            headerText.innerText = 'Now Playing';
        } else if (state.music.status === 'paused') {
            dot.className = 'status-dot afk';
            headerText.innerText = 'Paused';
        } else {
            dot.className = 'status-dot';
            headerText.innerText = 'Now Playing';
            titleEl.innerText = '休眠中';
            artistEl.innerText = '无播放任务';
        }
    }
}

const funFactPoolMouse = [
    (mm) => `💡 趣味统计：鼠标今天滑行的距离，相当于绕标准田径场跑了 ${(mm / 400).toFixed(1)} 圈。(一圈400米)`,
    (mm) => `💡 趣味统计：今日鼠标总位移，大约相当于攀爬了 ${(mm / 828).toFixed(1)} 座迪拜哈利法塔。(高828米)`,
    (mm) => `💡 趣味统计：鼠标今天在桌面上，相当于帮你跨越了 ${(mm / 632).toFixed(1)} 个上海中心大厦的高度。`,
    (mm) => `💡 趣味统计：鼠标滑行距离，相当于横跨了 ${(mm / 2737 * 100).toFixed(1)}% 的旧金山金门大桥。`,
    (mm) => `💡 趣味统计：鼠标今天走过的路程，相当于首尾相连停放了 ${(mm / 4.5).toFixed(0)} 辆家用小轿车。`
];

const funFactPoolScroll = [
    (sm) => `💡 趣味统计：你的滚轮今天滚动的距离，相当于 ${(sm / 3.05).toFixed(1)} 个标准篮球筐的高度。`,
    (sm) => `💡 趣味统计：今日滚轮累计滚动距离，大约有 ${(sm / 2).toFixed(1)} 扇标准家用木门那么高。`,
    (sm) => `💡 趣味统计：滚轮滚动里程，相当于一辆成人自行车的 ${(sm / 1.8).toFixed(1)} 倍长度。`,
    (sm) => `💡 趣味统计：滚轮今天大概滚动了 ${(sm / 0.75).toFixed(1)} 个标准篮球的周长。`,
    (sm) => `💡 趣味统计：今日滚轮已相当于在一张标准斯诺克台球桌上滚动了 ${(sm / 3.56).toFixed(1)} 个长边。`
];

function renderOdometer(isOffline) {
    if (!state.odometer) return;
    
    chartGaugeMouse.setOption(getGaugeOption('鼠标位移', 'M', '#00f2fe', 2000, state.odometer.mouse_meters));
    chartGaugeScroll.setOption(getGaugeOption('滚轮滚动', 'M', '#ff0844', 5, state.odometer.scroll_meters));
    
    if(!state.selectedFunFact) {
        const isScrollFact = Math.random() > 0.5;
        if (isScrollFact) {
            const randomIndex = Math.floor(Math.random() * funFactPoolScroll.length);
            state.selectedFunFact = funFactPoolScroll[randomIndex];
            state.isFunFactSourceScroll = true; 
        } else {
            const randomIndex = Math.floor(Math.random() * funFactPoolMouse.length);
            state.selectedFunFact = funFactPoolMouse[randomIndex];
            state.isFunFactSourceScroll = false;
        }
    }
    
    if (state.isFunFactSourceScroll) {
        document.getElementById('odo-subtext').innerText = state.selectedFunFact(state.odometer.scroll_meters);
    } else {
        document.getElementById('odo-subtext').innerText = state.selectedFunFact(state.odometer.mouse_meters);
    }
    
    const card = document.getElementById('card-odometer');
    if (isOffline) { card.className = 'card full-width offline-mode'; }
    else { card.className = 'card full-width'; }
}

window.addEventListener('resize', () => { 
    chartKeyboard.resize(); 
    chartMouse.resize(); 
    chartGaugeMouse.resize();
    chartGaugeScroll.resize(); 
});

// 工具函数
function formatRelativeTime(isoString) {
    if (!isoString) return '等待数据...';
    const diffSeconds = Math.floor((new Date() - new Date(isoString)) / 1000);
    if (diffSeconds < 60) return `${diffSeconds} 秒前`;
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
    return `${Math.floor(diffMinutes / 60)} 小时 ${diffMinutes % 60} 分钟前`;
}

function formatDuration(totalSeconds) {
    if (totalSeconds < 60) return `已持续 ${Math.floor(totalSeconds)} 秒`;
    const mins = Math.floor(totalSeconds / 60);
    if (mins < 60) return `已持续 ${mins} 分钟`;
    return `已持续 ${Math.floor(mins / 60)} 小时 ${mins % 60} 分钟`;
}

// 5. 全局渲染引擎
setInterval(() => {
    const now = new Date();
    let globalIsOffline = true;
    let diffAppSeconds = 0;

    if (state.app) {
        diffAppSeconds = (now - new Date(state.app.last_updated)) / 1000;
        globalIsOffline = diffAppSeconds > OFFLINE_THRESHOLD_SECONDS;
    }

    renderApp(globalIsOffline, diffAppSeconds);
    renderMusic(globalIsOffline);
    renderOdometer(globalIsOffline); 
    
    const cardKb = document.getElementById('card-keyboard');
    const cardMs = document.getElementById('card-mouse');
    if (globalIsOffline) { cardKb.className = 'card offline-mode'; cardMs.className = 'card offline-mode'; } 
    else { cardKb.className = 'card'; cardMs.className = 'card'; }

    if(state.input) {
        const t = formatRelativeTime(state.input);
        document.getElementById('time-input').innerText = t;
        document.getElementById('time-input-mouse').innerText = t;
        document.getElementById('time-odo').innerText = t;
    }
}, 1000);