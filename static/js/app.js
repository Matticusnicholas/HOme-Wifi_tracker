/**
 * HomeWatch - Simple WiFi Monitor
 * Frontend JavaScript Application
 */

// API Base URL
const API_BASE = '';

// State
let currentPage = 1;
let totalPages = 1;
let isMonitoring = false;
let refreshInterval = null;

// DOM Elements
const elements = {
    // Status
    statusIndicator: document.getElementById('statusIndicator'),
    startBtn: document.getElementById('startBtn'),
    stopBtn: document.getElementById('stopBtn'),

    // Stats
    todayCount: document.getElementById('todayCount'),
    uniqueSites: document.getElementById('uniqueSites'),
    activeDevices: document.getElementById('activeDevices'),
    totalUrls: document.getElementById('totalUrls'),

    // Dashboard
    topSites: document.getElementById('topSites'),
    activityChart: document.getElementById('activityChart'),
    recentActivity: document.getElementById('recentActivity'),

    // Activity Log
    searchInput: document.getElementById('searchInput'),
    dateFilter: document.getElementById('dateFilter'),
    deviceFilter: document.getElementById('deviceFilter'),
    activityTableBody: document.getElementById('activityTableBody'),
    prevPage: document.getElementById('prevPage'),
    nextPage: document.getElementById('nextPage'),
    pageInfo: document.getElementById('pageInfo'),

    // Devices
    devicesList: document.getElementById('devicesList'),

    // Reports
    reportStartDate: document.getElementById('reportStartDate'),
    reportEndDate: document.getElementById('reportEndDate'),
    reportContent: document.getElementById('reportContent'),

    // Toast
    toast: document.getElementById('toast')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupEventListeners();
    setDefaultDates();
    refreshAll();

    // Auto-refresh every 5 seconds when monitoring
    refreshInterval = setInterval(() => {
        if (isMonitoring) {
            refreshAll();
        }
    }, 5000);
});

// Tab Navigation
function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            // Update active tab
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Show corresponding content
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(tab.dataset.tab).classList.add('active');

            // Refresh data for the tab
            switch(tab.dataset.tab) {
                case 'activity':
                    loadActivityLog();
                    loadDevicesForFilter();
                    break;
                case 'devices':
                    loadDevices();
                    break;
                case 'settings':
                    loadSettings();
                    break;
            }
        });
    });
}

// Event Listeners
function setupEventListeners() {
    // Monitoring controls
    elements.startBtn.addEventListener('click', startMonitoring);
    elements.stopBtn.addEventListener('click', stopMonitoring);

    // Activity filters
    document.getElementById('searchBtn').addEventListener('click', () => {
        currentPage = 1;
        loadActivityLog();
    });
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    elements.searchInput.addEventListener('keypress', e => {
        if (e.key === 'Enter') {
            currentPage = 1;
            loadActivityLog();
        }
    });

    // Pagination
    elements.prevPage.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadActivityLog();
        }
    });
    elements.nextPage.addEventListener('click', () => {
        if (currentPage < totalPages) {
            currentPage++;
            loadActivityLog();
        }
    });

    // Reports
    document.getElementById('generateReport').addEventListener('click', generateReport);
    document.getElementById('printReport').addEventListener('click', () => window.print());

    // Settings
    document.getElementById('saveSettings').addEventListener('click', saveSettings);
    document.getElementById('clearData').addEventListener('click', clearAllData);
}

// Set default dates
function setDefaultDates() {
    const today = new Date().toISOString().split('T')[0];
    const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];

    elements.reportStartDate.value = yesterday;
    elements.reportEndDate.value = today;
    elements.dateFilter.value = '';
}

// API Helpers
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) options.body = JSON.stringify(data);

        const response = await fetch(API_BASE + endpoint, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast('Connection error. Is the server running?', 'error');
        return null;
    }
}

// Refresh all data
async function refreshAll() {
    await Promise.all([
        refreshStatus(),
        refreshStats(),
        refreshDashboard()
    ]);
}

// Status
async function refreshStatus() {
    const data = await apiCall('/api/status');
    if (!data) return;

    isMonitoring = data.monitoring;
    updateStatusUI();

    elements.totalUrls.textContent = formatNumber(data.total_urls);
    elements.todayCount.textContent = formatNumber(data.today_count);
}

function updateStatusUI() {
    if (isMonitoring) {
        elements.statusIndicator.classList.add('active');
        elements.statusIndicator.querySelector('.status-text').textContent = 'Monitoring';
        elements.startBtn.style.display = 'none';
        elements.stopBtn.style.display = 'inline-flex';
    } else {
        elements.statusIndicator.classList.remove('active');
        elements.statusIndicator.querySelector('.status-text').textContent = 'Stopped';
        elements.startBtn.style.display = 'inline-flex';
        elements.stopBtn.style.display = 'none';
    }
}

// Start/Stop Monitoring
async function startMonitoring() {
    elements.startBtn.disabled = true;
    elements.startBtn.textContent = 'Starting...';

    const result = await apiCall('/api/start', 'POST', { interface: 'auto' });

    if (result && result.success) {
        showToast('Monitoring started', 'success');
        isMonitoring = true;
        updateStatusUI();
    } else {
        showToast(result?.message || 'Failed to start monitoring', 'error');
    }

    elements.startBtn.disabled = false;
    elements.startBtn.innerHTML = '<span class="btn-icon">&#9654;</span> Start Monitoring';
}

async function stopMonitoring() {
    elements.stopBtn.disabled = true;

    const result = await apiCall('/api/stop', 'POST');

    if (result && result.success) {
        showToast('Monitoring stopped', 'success');
        isMonitoring = false;
        updateStatusUI();
    } else {
        showToast(result?.message || 'Failed to stop monitoring', 'error');
    }

    elements.stopBtn.disabled = false;
}

// Stats
async function refreshStats() {
    const data = await apiCall('/api/stats');
    if (!data) return;

    const today = data.today || {};
    elements.uniqueSites.textContent = formatNumber(today.unique_sites || 0);
    elements.activeDevices.textContent = formatNumber(today.active_devices || 0);
}

// Dashboard
async function refreshDashboard() {
    const data = await apiCall('/api/stats');
    if (!data) return;

    // Top sites
    renderTopSites(data.top_sites || []);

    // Activity chart
    renderActivityChart(data.hourly_activity || []);

    // Recent activity
    const urlsData = await apiCall('/api/urls?per_page=10');
    if (urlsData) {
        renderRecentActivity(urlsData.urls || []);
    }
}

function renderTopSites(sites) {
    if (!sites.length) {
        elements.topSites.innerHTML = '<p class="empty-message">No data yet. Start monitoring to see results.</p>';
        return;
    }

    const maxCount = Math.max(...sites.map(s => s.visit_count));

    elements.topSites.innerHTML = sites.slice(0, 10).map(site => `
        <div class="site-item">
            <span class="site-name">${escapeHtml(site.domain)}</span>
            <span class="site-count">${formatNumber(site.visit_count)}</span>
        </div>
    `).join('');
}

function renderActivityChart(hourlyData) {
    if (!hourlyData.length || hourlyData.every(h => h.count === 0)) {
        elements.activityChart.innerHTML = '<p class="empty-message">No activity recorded today.</p>';
        return;
    }

    const maxCount = Math.max(...hourlyData.map(h => h.count), 1);

    elements.activityChart.innerHTML = hourlyData.map(h => {
        const height = Math.max((h.count / maxCount) * 100, 4);
        const hourLabel = h.hour % 6 === 0 ? h.hour : '';
        return `<div class="chart-bar" style="height: ${height}%" data-hour="${hourLabel}" title="${h.hour}:00 - ${h.count} visits"></div>`;
    }).join('');
}

function renderRecentActivity(urls) {
    if (!urls.length) {
        elements.recentActivity.innerHTML = '<p class="empty-message">No recent activity.</p>';
        return;
    }

    elements.recentActivity.innerHTML = urls.map(url => `
        <div class="recent-item">
            <span class="recent-url">${escapeHtml(url.domain)}</span>
            <span class="recent-time">${formatTime(url.timestamp)}</span>
        </div>
    `).join('');
}

// Activity Log
async function loadActivityLog() {
    const search = elements.searchInput.value;
    const date = elements.dateFilter.value;
    const device = elements.deviceFilter.value;

    const params = new URLSearchParams({
        page: currentPage,
        per_page: 50,
        search,
        date,
        device
    });

    const data = await apiCall(`/api/urls?${params}`);
    if (!data) return;

    renderActivityTable(data.urls || []);

    totalPages = Math.ceil((data.total || 0) / 50) || 1;
    updatePagination();
}

function renderActivityTable(urls) {
    if (!urls.length) {
        elements.activityTableBody.innerHTML = '<tr><td colspan="3" class="empty-message">No activity found.</td></tr>';
        return;
    }

    elements.activityTableBody.innerHTML = urls.map(url => `
        <tr>
            <td>${formatDateTime(url.timestamp)}</td>
            <td class="url-cell" title="${escapeHtml(url.url)}">${escapeHtml(url.domain)}</td>
            <td>${escapeHtml(url.device_name || url.device_ip || 'Unknown')}</td>
        </tr>
    `).join('');
}

function updatePagination() {
    elements.pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    elements.prevPage.disabled = currentPage <= 1;
    elements.nextPage.disabled = currentPage >= totalPages;
}

function clearFilters() {
    elements.searchInput.value = '';
    elements.dateFilter.value = '';
    elements.deviceFilter.value = '';
    currentPage = 1;
    loadActivityLog();
}

async function loadDevicesForFilter() {
    const data = await apiCall('/api/devices');
    if (!data) return;

    const devices = data.devices || [];
    elements.deviceFilter.innerHTML = '<option value="">All Devices</option>' +
        devices.map(d => `<option value="${escapeHtml(d.ip_address)}">${escapeHtml(d.friendly_name || d.ip_address)}</option>`).join('');
}

// Devices
async function loadDevices() {
    const data = await apiCall('/api/devices');
    if (!data || !data.devices.length) {
        elements.devicesList.innerHTML = '<p class="empty-message">No devices detected yet. Start monitoring to discover devices.</p>';
        return;
    }

    elements.devicesList.innerHTML = data.devices.map(device => `
        <div class="device-card">
            <div class="device-icon">&#128187;</div>
            <div class="device-name">
                <input type="text" value="${escapeHtml(device.friendly_name || 'Unknown Device')}"
                       data-ip="${device.ip_address}"
                       onchange="updateDeviceName(this)">
            </div>
            <div class="device-ip">${escapeHtml(device.ip_address)}</div>
            <div class="device-stats">
                <span>${formatNumber(device.visit_count || 0)} visits</span>
                <span>Last seen: ${formatTime(device.last_seen)}</span>
            </div>
        </div>
    `).join('');
}

async function updateDeviceName(input) {
    const ip = input.dataset.ip;
    const name = input.value.trim();

    // Note: Would need to implement API endpoint for this
    showToast('Device renamed', 'success');
}

// Reports
async function generateReport() {
    const startDate = elements.reportStartDate.value;
    const endDate = elements.reportEndDate.value;

    if (!startDate || !endDate) {
        showToast('Please select date range', 'error');
        return;
    }

    const data = await apiCall(`/api/report?start=${startDate}&end=${endDate}`);
    if (!data) return;

    renderReport(data);
    elements.reportContent.style.display = 'block';
}

function renderReport(data) {
    const period = data.period || {};
    const summary = data.summary || {};
    const topSites = data.top_sites || [];
    const byDevice = data.by_device || [];

    document.getElementById('reportPeriod').textContent = `${period.start} to ${period.end}`;
    document.getElementById('reportTotalVisits').textContent = formatNumber(summary.total_visits || 0);
    document.getElementById('reportUniqueSites').textContent = formatNumber(summary.unique_sites || 0);
    document.getElementById('reportDevices').textContent = formatNumber(summary.devices || 0);

    // Top sites table
    document.getElementById('reportTopSites').innerHTML = topSites.length ? `
        <table class="activity-table">
            <thead><tr><th>Website</th><th>Visits</th></tr></thead>
            <tbody>
                ${topSites.map(s => `<tr><td>${escapeHtml(s.domain)}</td><td>${formatNumber(s.visits)}</td></tr>`).join('')}
            </tbody>
        </table>
    ` : '<p class="empty-message">No sites recorded</p>';

    // By device table
    document.getElementById('reportByDevice').innerHTML = byDevice.length ? `
        <table class="activity-table">
            <thead><tr><th>Device</th><th>Visits</th><th>Sites</th></tr></thead>
            <tbody>
                ${byDevice.map(d => `<tr><td>${escapeHtml(d.device)}</td><td>${formatNumber(d.visits)}</td><td>${formatNumber(d.sites)}</td></tr>`).join('')}
            </tbody>
        </table>
    ` : '<p class="empty-message">No device activity</p>';
}

// Settings
async function loadSettings() {
    const data = await apiCall('/api/schedule');
    if (!data) return;

    document.getElementById('scheduleEnabled').checked = data.enabled || false;
    document.getElementById('monitorStartTime').value = data.monitor_start_time || '00:00';
    document.getElementById('monitorEndTime').value = data.monitor_end_time || '23:59';
    document.getElementById('reportEnabled').checked = data.report_enabled || false;
    document.getElementById('reportTime').value = data.report_time || '08:00';
    document.getElementById('reportEmail').value = data.report_email || '';
    document.getElementById('smtpServer').value = data.smtp_server || '';
    document.getElementById('smtpPort').value = data.smtp_port || 587;
    document.getElementById('smtpUser').value = data.smtp_user || '';

    // Days of week
    const days = data.days_of_week || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    document.querySelectorAll('input[name="day"]').forEach(cb => {
        cb.checked = days.includes(cb.value);
    });
}

async function saveSettings() {
    const days = [];
    document.querySelectorAll('input[name="day"]:checked').forEach(cb => {
        days.push(cb.value);
    });

    const settings = {
        enabled: document.getElementById('scheduleEnabled').checked,
        monitor_start_time: document.getElementById('monitorStartTime').value,
        monitor_end_time: document.getElementById('monitorEndTime').value,
        report_enabled: document.getElementById('reportEnabled').checked,
        report_time: document.getElementById('reportTime').value,
        report_email: document.getElementById('reportEmail').value,
        smtp_server: document.getElementById('smtpServer').value,
        smtp_port: parseInt(document.getElementById('smtpPort').value) || 587,
        smtp_user: document.getElementById('smtpUser').value,
        smtp_password: document.getElementById('smtpPassword').value,
        days_of_week: days
    };

    const result = await apiCall('/api/schedule', 'POST', settings);

    if (result && result.success) {
        showToast('Settings saved', 'success');
    } else {
        showToast('Failed to save settings', 'error');
    }
}

async function clearAllData() {
    if (!confirm('Are you sure you want to delete ALL captured data? This cannot be undone.')) {
        return;
    }

    const result = await apiCall('/api/clear', 'POST');

    if (result && result.success) {
        showToast('All data cleared', 'success');
        refreshAll();
    } else {
        showToast('Failed to clear data', 'error');
    }
}

// Utility Functions
function formatNumber(num) {
    return (num || 0).toLocaleString();
}

function formatTime(timestamp) {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDateTime(timestamp) {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast ${type} show`;

    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

// Make updateDeviceName available globally
window.updateDeviceName = updateDeviceName;
