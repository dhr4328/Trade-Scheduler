// Initialize chart variables
let chart = null;
let candleSeries = null;
let sbtSeries = null;
let bbUpSeries = null;
let bbDnSeries = null;
let isInitialized = false;

// DOM Elements
const kpiSymbol = document.getElementById('kpi-symbol');
const kpiPrice = document.getElementById('kpi-price');
const kpiSbt = document.getElementById('kpi-sbt');
const kpiSignal = document.getElementById('kpi-signal');
const refreshBtn = document.getElementById('refresh-btn');
const chartLoader = document.getElementById('chart-loader');
const chartContainer = document.getElementById('chart');

// Refresh click binding
refreshBtn.addEventListener('click', () => {
    refreshBtn.classList.add('loading');
    refreshBtn.querySelector('.icon').style.transform = 'rotate(180deg)';
    refreshBtn.querySelector('.icon').style.transition = 'transform 0.5s ease';
    fetchBotData();
});

// Setup Lightweight Charts
function initChart() {
    chart = LightweightCharts.createChart(chartContainer, {
        layout: {
            background: { type: 'solid', color: 'transparent' },
            textColor: '#94a3b8',
            fontFamily: 'Inter',
        },
        grid: {
            vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
            horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                width: 1,
                color: 'rgba(59, 130, 246, 0.5)',
                style: 3, // dashed
                labelBackgroundColor: '#3b82f6',
            },
            horzLine: {
                width: 1,
                color: 'rgba(59, 130, 246, 0.5)',
                style: 3,
                labelBackgroundColor: '#3b82f6',
            },
        },
        timeScale: {
            borderColor: 'rgba(255, 255, 255, 0.1)',
            timeVisible: true,
            secondsVisible: false,
        },
        rightPriceScale: {
            borderColor: 'rgba(255, 255, 255, 0.1)',
        },
    });

    // Strategy Series Mapping
    candleSeries = chart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
        borderDownColor: '#ef4444',
        borderUpColor: '#10b981',
        wickDownColor: '#ef4444',
        wickUpColor: '#10b981',
    });

    bbUpSeries = chart.addLineSeries({
        color: 'rgba(59, 130, 246, 0.3)',
        lineWidth: 1,
        lineStyle: 2, // Dashed
        crosshairMarkerVisible: false,
        lastValueVisible: false,
    });

    bbDnSeries = chart.addLineSeries({
        color: 'rgba(59, 130, 246, 0.3)',
        lineWidth: 1,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
    });

    sbtSeries = chart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 2,
        crosshairMarkerVisible: true,
    });

    // Resize handling
    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainer) { return; }
        const newRect = entries[0].contentRect;
        chart.applyOptions({ height: newRect.height, width: newRect.width });
    }).observe(chartContainer);

    isInitialized = true;
}

// Map signals for colors and formatting
function formatSignal(signal) {
    if (!signal || signal === "NONE") return { text: "Monitoring...", class: "val-neu" };
    if (signal === "LONG") return { text: "BUY / LONG 🟢", class: "val-up" };
    if (signal === "SHORT") return { text: "SELL / SHORT 🔴", class: "val-dn" };
    return { text: signal, class: "val-neu" };
}

// Fetch Core Data
async function fetchBotData() {
    try {
        if(!isInitialized) chartLoader.style.display = 'flex';
        
        const res = await fetch('/api/bot-data');
        if (!res.ok) throw new Error('Network response was not ok');
        const data = await res.json();

        // Hide Loader
        chartLoader.style.display = 'none';
        
        // Update KPIs
        kpiSymbol.textContent = data.symbol;
        kpiPrice.textContent = `₹ ${data.latest_price.toFixed(2)}`;
        
        // Coloring for Price vs SBT
        if (data.latest_price > data.latest_sbt) {
            kpiPrice.classList.remove('val-dn'); kpiPrice.classList.add('val-up');
        } else {
            kpiPrice.classList.remove('val-up'); kpiPrice.classList.add('val-dn');
        }

        kpiSbt.textContent = data.latest_sbt.toFixed(2);
        
        const signalFmt = formatSignal(data.latest_signal);
        kpiSignal.textContent = signalFmt.text;
        kpiSignal.className = `kpi-value ${signalFmt.class}`;

        // Prepare Chart Data
        const candles = [];
        const srSbt = [];
        const srBbUp = [];
        const srBbDn = [];
        const markers = [];

        data.chart_data.forEach(item => {
            candles.push({ time: item.time, open: item.open, high: item.high, low: item.low, close: item.close });
            if (item.sbt) srSbt.push({ time: item.time, value: item.sbt });
            if (item.bb_up) srBbUp.push({ time: item.time, value: item.bb_up });
            if (item.bb_dn) srBbDn.push({ time: item.time, value: item.bb_dn });
            
            // Add Signals to chart UI
            if (item.signal === "LONG") {
                markers.push({
                    time: item.time,
                    position: 'belowBar',
                    color: '#10b981',
                    shape: 'arrowUp',
                    text: 'BUY',
                    size: 2
                });
            } else if (item.signal === "SHORT") {
                markers.push({
                    time: item.time,
                    position: 'aboveBar',
                    color: '#ef4444',
                    shape: 'arrowDown',
                    text: 'SELL',
                    size: 2
                });
            }
        });

        // Initialize Chart if needed
        if (!isInitialized) initChart();

        // Update Series
        candleSeries.setData(candles);
        sbtSeries.setData(srSbt);
        bbUpSeries.setData(srBbUp);
        bbDnSeries.setData(srBbDn);
        
        // Set Markers
        candleSeries.setMarkers(markers);

        // Reset transform on sync button
        setTimeout(() => {
            refreshBtn.querySelector('.icon').style.transform = 'rotate(0deg)';
        }, 500);

    } catch (error) {
        console.error("Error fetching data:", error);
        chartLoader.querySelector('p').textContent = "Error connecting to Core Logic. Retrying...";
        setTimeout(fetchBotData, 5000);
    }
}

// Start
document.addEventListener('DOMContentLoaded', () => {
    fetchBotData();
    // Auto refresh every 1 minute
    setInterval(fetchBotData, 60000);
});
