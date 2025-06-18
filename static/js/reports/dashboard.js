// static/js/reports/dashboard.js

class DashboardManager {
    constructor() {
        this.charts = {};
        this.filters = {
            timeRange: '30',
            targetType: 'all'
        };
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadDashboard();
    }

    setupEventListeners() {
        // Filter controls
        document.getElementById('timeRange').addEventListener('change', (e) => {
            this.filters.timeRange = e.target.value;
            this.loadDashboard();
        });

        document.getElementById('targetType').addEventListener('change', (e) => {
            this.filters.targetType = e.target.value;
            this.loadDashboard();
        });

        document.getElementById('refreshDashboard').addEventListener('click', () => {
            this.loadDashboard();
        });

        // Chart toggles
        document.getElementById('showEndpoints').addEventListener('change', () => {
            this.updateTimelineChart();
        });

        document.getElementById('showChains').addEventListener('change', () => {
            this.updateTimelineChart();
        });

        // Performance metric selector
        document.getElementById('performanceMetric').addEventListener('change', () => {
            this.loadTopPerformers();
        });

        document.getElementById('problemMetric').addEventListener('change', () => {
            this.loadProblemAreas();
        });

        document.getElementById('chainSelector').addEventListener('change', () => {
            this.loadChainAnalysis();
        });
    }

    async loadDashboard() {
        try {
            // Show loading state
            this.showLoading();

            console.log('Loading dashboard data...');
            console.log('Three.js available:', typeof THREE !== 'undefined');
            console.log('CyberpunkViz available:', typeof window.cyberpunkViz !== 'undefined');

            // Load all dashboard data in parallel
            await Promise.all([
                this.loadOverviewMetrics(),
                this.loadDistributionChart(),
                this.loadTimelineChart(),
                this.loadTopPerformers(),
                this.loadProblemAreas(),
                this.loadStatusCodeHeatmap(),
                this.loadRecentActivity(),
                this.loadChainAnalysis()
            ]);

            // Hide loading state
            this.hideLoading();
        } catch (error) {
            console.error('Error loading dashboard:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    async loadOverviewMetrics() {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(`/reports/api/overview?${params}`);
        const data = await response.json();

        // Update metric cards
        document.getElementById('totalTests').textContent = data.total_tests.toLocaleString();
        document.getElementById('successRate').textContent = `${data.success_rate}%`;
        document.getElementById('avgDuration').textContent = `${data.avg_duration}ms`;
        document.getElementById('activeEndpoints').textContent = data.active_endpoints;

        // Update change indicators
        this.updateChangeIndicator('testsChange', data.changes.tests);
        this.updateChangeIndicator('successRateChange', data.changes.success_rate);
        this.updateChangeIndicator('durationChange', data.changes.duration);
        this.updateChangeIndicator('endpointsChange', data.changes.endpoints);
    }

    updateChangeIndicator(elementId, change) {
        const element = document.getElementById(elementId);
        if (change > 0) {
            element.className = 'metric-change positive';
            element.textContent = `+${change.toFixed(1)}%`;
        } else if (change < 0) {
            element.className = 'metric-change negative';
            element.textContent = `${change.toFixed(1)}%`;
        } else {
            element.className = 'metric-change';
            element.textContent = 'No change';
        }
    }

    async loadDistributionChart() {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(`/reports/api/distribution?${params}`);
        const data = await response.json();

        // Use the new cyberpunk canvas visualization
        if (window.cyberpunkCanvas) {
            this.loadCyberpunkDistributionChart(data);
        } else {
            this.loadTraditional2DChart(data);
        }
    }

    loadCyberpunkDistributionChart(data) {
        console.log('Loading Cyberpunk Canvas distribution chart...');
        
        // Prepare data for canvas visualization
        const chartData = [
            { label: 'EP-Pass', value: data.endpoint_tests.passed },
            { label: 'EP-Fail', value: data.endpoint_tests.failed },
            { label: 'EP-Skip', value: data.endpoint_tests.skipped },
            { label: 'EP-Pend', value: data.endpoint_tests.pending_review },
            { label: 'CH-Pass', value: data.chain_tests.passed },
            { label: 'CH-Fail', value: data.chain_tests.failed },
            { label: 'CH-Skip', value: data.chain_tests.skipped },
            { label: 'CH-Pend', value: data.chain_tests.pending_review }
        ].filter(item => item.value > 0);

        // If no real data, create demo data
        if (chartData.length === 0) {
            chartData.push(
                { label: 'TESTS-PASS', value: 156 },
                { label: 'TESTS-FAIL', value: 23 },
                { label: 'TESTS-WARN', value: 8 },
                { label: 'TESTS-PEND', value: 12 }
            );
        }

        console.log('Creating holographic pie chart with data:', chartData);

        // Clean up existing chart
        if (this.charts.distributionCanvas) {
            window.cyberpunkCanvas.destroy('distributionChartContainer');
        }

        // Create cyberpunk canvas pie chart
        this.charts.distributionCanvas = window.cyberpunkCanvas.createHoloPieChart('distributionChartContainer', chartData, {
            showParticles: true,
            showScanlines: true,
            animated: true
        });

        console.log('Cyberpunk holographic pie chart created!');
    }

    loadTraditional2DChart(data) {
        // Fallback to traditional 2D chart if 3D is not available
        const container = document.getElementById('distributionChartContainer');
        let canvas = container.querySelector('canvas');
        if (!canvas) {
            // Create canvas if it doesn't exist
            canvas = document.createElement('canvas');
            container.appendChild(canvas);
        }
        const ctx = canvas.getContext('2d');

        // Destroy existing chart
        if (this.charts.distribution) {
            this.charts.distribution.destroy();
        }

        this.charts.distribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: [
                    'Endpoint Passed', 'Endpoint Failed', 'Endpoint Skipped', 'Endpoint Pending',
                    'Chain Passed', 'Chain Failed', 'Chain Skipped', 'Chain Pending'
                ],
                datasets: [{
                    data: [
                        data.endpoint_tests.passed,
                        data.endpoint_tests.failed,
                        data.endpoint_tests.skipped,
                        data.endpoint_tests.pending_review,
                        data.chain_tests.passed,
                        data.chain_tests.failed,
                        data.chain_tests.skipped,
                        data.chain_tests.pending_review
                    ],
                    backgroundColor: [
                        '#00ff41', '#ff3030', '#ffff00', '#ff0099',
                        '#0099ff', '#ff0000', '#00ffaa', '#aa00ff'
                    ],
                    borderWidth: 2,
                    borderColor: '#000000'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            usePointStyle: true,
                            padding: 20,
                            color: '#00ff41'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#00ff41',
                        bodyColor: '#ffffff',
                        borderColor: '#00ff41',
                        borderWidth: 1,
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.raw / total) * 100).toFixed(1);
                                return `${context.label}: ${context.raw} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '60%'
            }
        });
    }

    async loadTimelineChart() {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(`/reports/api/timeline?${params}`);
        const data = await response.json();

        this.timelineData = data;
        this.updateTimelineChart();
    }

    updateTimelineChart() {
        const showEndpoints = document.getElementById('showEndpoints').checked;
        const showChains = document.getElementById('showChains').checked;

        const ctx = document.getElementById('timelineChart').getContext('2d');

        // Destroy existing chart
        if (this.charts.timeline) {
            this.charts.timeline.destroy();
        }

        const datasets = [];

        if (showEndpoints) {
            datasets.push({
                label: 'Endpoint Success Rate',
                data: this.timelineData.map(d => d.endpoint_success_rate),
                borderColor: '#4BC0C0',
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                fill: false,
                tension: 0.4
            });
        }

        if (showChains) {
            datasets.push({
                label: 'Chain Success Rate',
                data: this.timelineData.map(d => d.chain_success_rate),
                borderColor: '#10B981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: false,
                tension: 0.4
            });
        }

        this.charts.timeline = new Chart(ctx, {
            type: 'line',
            data: { 
                labels: this.timelineData.map(d => new Date(d.date).toLocaleDateString()),
                datasets 
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9CA3AF'
                        }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9CA3AF',
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#ffffff'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: ${context.raw.toFixed(1)}%`;
                            }
                        }
                    }
                }
            }
        });
    }

    async loadTopPerformers() {
        const metric = document.getElementById('performanceMetric').value;
        const params = new URLSearchParams({
            ...this.filters,
            metric
        });
        const response = await fetch(`/reports/api/top_performers?${params}`);
        const data = await response.json();

        // Use cyberpunk canvas for top performers
        if (window.cyberpunkCanvas && data.length > 0) {
            const metricKey = metric === 'success_rate' ? 'success_rate' : 
                             metric === 'execution_count' ? 'execution_count' : 'avg_duration';
            
            const chartData = data.slice(0, 8).map(d => ({
                label: d.name.substring(0, 12),
                value: Math.round(d[metricKey])
            }));

            if (this.charts.topPerformersCanvas) {
                // Use the container ID for destruction
                window.cyberpunkCanvas.destroy('topPerformersChartContainer');
            }

            this.charts.topPerformersCanvas = window.cyberpunkCanvas.createCyberBarChart('topPerformersChartContainer', chartData, {
                horizontal: true,
                metric: metric
            });

            console.log('Cyberpunk top performers chart created');
            return;
        }

        // Fallback to regular chart
        const container = document.getElementById('topPerformersChartContainer');
        container.innerHTML = ''; // Clear the container first
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        const ctx = canvas.getContext('2d');

        if (this.charts.topPerformers) {
            this.charts.topPerformers.destroy();
        }

        const metricKey = metric === 'success_rate' ? 'success_rate' : 
                          metric === 'execution_count' ? 'execution_count' : 'avg_duration';

        this.charts.topPerformers = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => `${d.name} (${d.type})`),
                datasets: [{
                    data: data.map(d => d[metricKey]),
                    backgroundColor: data.map(d => 
                        d.type === 'Chain' ? '#00ff41' : '#0099ff'
                    ),
                    borderWidth: 0
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#00ff41',
                        bodyColor: '#ffffff',
                        callbacks: {
                            label: function(context) {
                                const suffix = metric === 'success_rate' ? '%' : 
                                             metric === 'avg_duration' ? 'ms' : '';
                                return `${context.raw}${suffix}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(0, 255, 65, 0.2)'
                        },
                        ticks: {
                            color: '#00ff41'
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#00ff41'
                        }
                    }
                }
            }
        });
    }

    async loadProblemAreas() {
        const metric = document.getElementById('problemMetric').value;
        const params = new URLSearchParams({
            ...this.filters,
            metric
        });
        const response = await fetch(`/reports/api/problem_areas?${params}`);
        const data = await response.json();

        const ctx = document.getElementById('problemAreasChart').getContext('2d');

        if (this.charts.problemAreas) {
            this.charts.problemAreas.destroy();
        }

        this.charts.problemAreas = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => `${d.name} (${d.type})`),
                datasets: [{
                    data: data.map(d => d[metric]),
                    backgroundColor: '#EF4444',
                    borderWidth: 0
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.raw.toFixed(1)}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9CA3AF',
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#9CA3AF'
                        }
                    }
                }
            }
        });
    }

    async loadStatusCodeHeatmap() {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(`/reports/api/status_codes?${params}`);
        const data = await response.json();

        const container = document.getElementById('statusHeatmap');
        container.innerHTML = '';

        const colors = {
            '2xx Success': '#10B981',
            '3xx Redirect': '#F59E0B',
            '4xx Client Error': '#EF4444',
            '5xx Server Error': '#DC2626',
            'Other': '#6B7280'
        };

        const total = Object.values(data).reduce((a, b) => a + b, 0);

        Object.entries(data).forEach(([status, count]) => {
            const cell = document.createElement('div');
            cell.className = 'heatmap-cell';
            cell.style.backgroundColor = colors[status] || '#6B7280';
            cell.textContent = `${status}\n${count}`;
            cell.title = `${status}: ${count} (${(count/total*100).toFixed(1)}%)`;
            
            cell.addEventListener('click', () => {
                this.showStatusCodeDetails(status, count);
            });
            
            container.appendChild(cell);
        });
    }

    async loadRecentActivity() {
        const response = await fetch('/reports/api/recent_activity?limit=10');
        const data = await response.json();

        const container = document.getElementById('recentActivity');
        container.innerHTML = '';

        data.forEach(activity => {
            const item = document.createElement('div');
            item.className = 'activity-item';

            const statusColors = {
                'passed': '#10B981',
                'failed': '#EF4444',
                'skipped': '#F59E0B',
                'pending_review': '#8B5CF6'
            };

            item.innerHTML = `
                <div class="activity-icon" style="background-color: ${statusColors[activity.status] || '#6B7280'}">
                    <i class="${activity.icon_class}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-title">${activity.title}</div>
                    <div class="activity-meta">
                        ${new Date(activity.created_at).toLocaleString()} • 
                        ${activity.duration ? activity.duration + 'ms' : 'No duration'}
                    </div>
                </div>
            `;

            container.appendChild(item);
        });
    }

    async loadChainAnalysis() {
        const chainId = document.getElementById('chainSelector').value;
        const params = new URLSearchParams({
            ...this.filters,
            chain_id: chainId
        });
        const response = await fetch(`/reports/api/chains/analysis?${params}`);
        const data = await response.json();

        const ctx = document.getElementById('chainAnalysisChart').getContext('2d');

        if (this.charts.chainAnalysis) {
            this.charts.chainAnalysis.destroy();
        }

        this.charts.chainAnalysis = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.step_analysis.map(s => s.step_name),
                datasets: [{
                    label: 'Success Rate',
                    data: data.step_analysis.map(s => s.success_rate),
                    backgroundColor: '#10B981',
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const stepData = data.step_analysis[context.dataIndex];
                                return [
                                    `Success Rate: ${context.raw.toFixed(1)}%`,
                                    `Total Executions: ${stepData.total_executions}`,
                                    `Successes: ${stepData.success_count}`,
                                    `Failures: ${stepData.failure_count}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9CA3AF'
                        }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9CA3AF',
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }

    showLoading() {
        // Add loading spinners to metric cards
        document.querySelectorAll('.metric-value').forEach(el => {
            el.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        });
    }

    hideLoading() {
        // Loading is automatically hidden when data is populated
    }

    showError(message) {
        // You could implement a toast notification here
        console.error(message);
    }

    showStatusCodeDetails(status, count) {
        // Implement detailed view for status codes
        alert(`${status}: ${count} occurrences`);
    }
}

// Global functions for modal and detailed views
function showChainDetails() {
    const chainId = document.getElementById('chainSelector').value;
    document.getElementById('chainDetailsModal').classList.add('modal-visible');
    // Load detailed chain data
}

function closeChainModal() {
    document.getElementById('chainDetailsModal').classList.remove('modal-visible');
}

function hideDetailedAnalysis() {
    document.getElementById('detailedAnalysis').style.display = 'none';
}

function exportChart(chartId) {
    // Implement chart export functionality
    console.log('Exporting chart:', chartId);
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing dashboard...');
    console.log('Chart availability:', typeof Chart);
    
    // Try immediate initialization first
    if (typeof Chart !== 'undefined') {
        console.log('Chart.js already available!');
        try {
            window.dashboardManager = new DashboardManager();
        } catch (error) {
            console.error('Error initializing dashboard:', error);
        }
    } else {
        // Wait a bit longer for Chart.js to load
        setTimeout(() => {
            console.log('After timeout, Chart availability:', typeof Chart);
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js loaded successfully!');
                try {
                    window.dashboardManager = new DashboardManager();
                } catch (error) {
                    console.error('Error initializing dashboard:', error);
                }
            } else {
                console.error('Chart.js still not available. Check the network tab.');
                const totalTestsEl = document.getElementById('totalTests');
                if (totalTestsEl) {
                    totalTestsEl.textContent = 'Error: Chart.js not loaded';
                }
            }
        }, 500);
    }
});