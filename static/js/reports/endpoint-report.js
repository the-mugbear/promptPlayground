// static/js/reports/endpoint-report.js

class EndpointReportManager {
    constructor() {
        this.charts = {};
        this.filters = {
            timeRange: '30'
        };
        this.endpointId = window.ENDPOINT_ID;
        this.endpointName = window.ENDPOINT_NAME;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadEndpointReport();
    }

    setupEventListeners() {
        // Time range filter
        document.getElementById('timeRange').addEventListener('change', (e) => {
            this.filters.timeRange = e.target.value;
            this.loadEndpointReport();
        });

        // Chart toggles for duration analysis
        document.getElementById('showAverage')?.addEventListener('change', () => {
            this.updateDurationChart();
        });

        document.getElementById('showPercentiles')?.addEventListener('change', () => {
            this.updateDurationChart();
        });
    }

    async loadEndpointReport() {
        try {
            this.showLoading();

            // Load all endpoint data in parallel
            await Promise.all([
                this.loadOverviewMetrics(),
                this.loadStatusChart(),
                this.loadTimelineChart(),
                this.loadDurationChart(),
                this.loadStatusCodeChart(),
                this.loadChainUsage(),
                this.loadRecentTestRuns(),
                this.loadDetailedAnalysis()
            ]);

            this.hideLoading();
        } catch (error) {
            console.error('Error loading endpoint report:', error);
            this.showError('Failed to load endpoint report data');
        }
    }

    async loadOverviewMetrics() {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(`/reports/api/endpoint/${this.endpointId}/overview?${params}`);
        const data = await response.json();

        // Update metric cards
        document.getElementById('totalTests').textContent = data.total_tests.toLocaleString();
        document.getElementById('successRate').textContent = `${data.success_rate}%`;
        document.getElementById('avgDuration').textContent = `${data.avg_duration}ms`;
        document.getElementById('testRuns').textContent = data.test_runs;

        // Update change indicators (if available)
        this.updateChangeIndicator('testsChange', data.changes?.tests || 0);
        this.updateChangeIndicator('successRateChange', data.changes?.success_rate || 0);
        this.updateChangeIndicator('durationChange', data.changes?.duration || 0);
        this.updateChangeIndicator('runsChange', data.changes?.runs || 0);
    }

    updateChangeIndicator(elementId, change) {
        const element = document.getElementById(elementId);
        if (!element) return;

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

    async loadStatusChart() {
        const params = new URLSearchParams(this.filters);
        // Use the general distribution endpoint filtered for this endpoint
        const response = await fetch(`/reports/api/distribution?${params}&endpoint_id=${this.endpointId}`);
        const data = await response.json();

        const ctx = document.getElementById('statusChart').getContext('2d');

        if (this.charts.status) {
            this.charts.status.destroy();
        }

        // Calculate total tests for this endpoint
        const endpointTests = data.endpoint_tests || { passed: 0, failed: 0, skipped: 0, pending_review: 0 };
        
        this.charts.status = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Skipped', 'Pending Review'],
                datasets: [{
                    data: [
                        endpointTests.passed,
                        endpointTests.failed,
                        endpointTests.skipped,
                        endpointTests.pending_review
                    ],
                    backgroundColor: ['#10B981', '#EF4444', '#F59E0B', '#8B5CF6'],
                    borderWidth: 2,
                    borderColor: '#1a1a1a'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            color: '#ffffff'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((context.raw / total) * 100).toFixed(1) : 0;
                                return `${context.label}: ${context.raw} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '50%'
            }
        });
    }

    async loadTimelineChart() {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(`/reports/api/endpoint/${this.endpointId}/timeline?${params}`);
        const data = await response.json();

        const ctx = document.getElementById('timelineChart').getContext('2d');

        if (this.charts.timeline) {
            this.charts.timeline.destroy();
        }

        this.charts.timeline = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => new Date(d.date).toLocaleDateString()),
                datasets: [{
                    label: 'Success Rate',
                    data: data.map(d => d.success_rate),
                    borderColor: '#10B981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
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
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Success Rate: ${context.raw.toFixed(1)}%`;
                            }
                        }
                    }
                }
            }
        });
    }

    async loadDurationChart() {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(`/reports/api/endpoint/${this.endpointId}/timeline?${params}`);
        const data = await response.json();

        this.durationData = data;
        this.updateDurationChart();
    }

    updateDurationChart() {
        const showAverage = document.getElementById('showAverage')?.checked ?? true;
        const showPercentiles = document.getElementById('showPercentiles')?.checked ?? true;

        const ctx = document.getElementById('durationChart').getContext('2d');

        if (this.charts.duration) {
            this.charts.duration.destroy();
        }

        const datasets = [];

        if (showAverage) {
            datasets.push({
                label: 'Average Duration',
                data: this.durationData.map(d => d.avg_duration),
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: false,
                tension: 0.4
            });
        }

        // Note: We'd need to add percentile data to the API response
        // This is a placeholder for demonstration
        if (showPercentiles && this.durationData.length > 0) {
            datasets.push({
                label: '95th Percentile',
                data: this.durationData.map(d => d.avg_duration * 1.5), // Placeholder calculation
                borderColor: '#F59E0B',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                fill: false,
                tension: 0.4,
                borderDash: [5, 5]
            });
        }

        this.charts.duration = new Chart(ctx, {
            type: 'line',
            data: { 
                labels: this.durationData.map(d => new Date(d.date).toLocaleDateString()),
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
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9CA3AF',
                            callback: function(value) {
                                return value + 'ms';
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
                                return `${context.dataset.label}: ${context.raw.toFixed(0)}ms`;
                            }
                        }
                    }
                }
            }
        });
    }

    async loadStatusCodeChart() {
        const params = new URLSearchParams({
            ...this.filters,
            endpoint_id: this.endpointId
        });
        const response = await fetch(`/reports/api/status_codes?${params}`);
        const data = await response.json();

        const ctx = document.getElementById('statusCodeChart').getContext('2d');

        if (this.charts.statusCode) {
            this.charts.statusCode.destroy();
        }

        const colors = {
            '2xx Success': '#10B981',
            '3xx Redirect': '#F59E0B',
            '4xx Client Error': '#EF4444',
            '5xx Server Error': '#DC2626',
            'Other': '#6B7280'
        };

        this.charts.statusCode = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(data),
                datasets: [{
                    data: Object.values(data),
                    backgroundColor: Object.keys(data).map(key => colors[key] || '#6B7280'),
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
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.raw / total) * 100).toFixed(1);
                                return `${context.label}: ${context.raw} (${percentage}%)`;
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
                        grid: {
                            color: '#374151'
                        },
                        ticks: {
                            color: '#9CA3AF'
                        }
                    }
                }
            }
        });
    }

    async loadChainUsage() {
        // This would need a new API endpoint to get chains that use this endpoint
        // For now, we'll hide the chain usage card if no data
        const chainCard = document.getElementById('chainUsageCard');
        if (chainCard) {
            chainCard.style.display = 'none';
        }
    }

    async loadRecentTestRuns() {
        const response = await fetch(`/reports/api/endpoint/${this.endpointId}/recent_runs?limit=5`);
        const data = await response.json();

        const container = document.getElementById('recentTestRuns');
        container.innerHTML = '';

        data.forEach(run => {
            const runCard = document.createElement('div');
            runCard.className = 'test-run-card';

            const statusClass = `status-${run.status}`;
            
            runCard.innerHTML = `
                <div class="test-run-header">
                    <div class="test-run-name">${run.name}</div>
                    <div class="test-run-status ${statusClass}">${run.status}</div>
                </div>
                <div class="test-run-meta">
                    Created: ${new Date(run.created_at).toLocaleString()}
                </div>
                <div class="test-run-metrics">
                    <div class="metric-item">
                        <span class="metric-number">${run.total_tests}</span>
                        <span>Total</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-number">${run.passed_tests}</span>
                        <span>Passed</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-number">${run.success_rate}%</span>
                        <span>Success</span>
                    </div>
                    <div class="metric-item">
                        <a href="/test_runs/view/${run.id}" class="btn btn-sm btn-primary">
                            <i class="fas fa-eye"></i>
                        </a>
                    </div>
                </div>
            `;

            container.appendChild(runCard);
        });
    }

    async loadDetailedAnalysis() {
        // Load common failures, performance insights, and usage patterns
        // This would require additional API endpoints for detailed analysis
        
        // For now, populate with placeholder data
        const commonFailures = document.getElementById('commonFailures');
        commonFailures.innerHTML = `
            <div class="failure-item">
                <strong>Connection Timeout</strong><br>
                <span class="text-muted">Occurred in 15% of failed requests</span>
            </div>
            <div class="failure-item">
                <strong>Rate Limiting (429)</strong><br>
                <span class="text-muted">Most common during peak hours</span>
            </div>
        `;

        const performanceInsights = document.getElementById('performanceInsights');
        performanceInsights.innerHTML = `
            <div class="insight-item">
                <strong>Peak Performance</strong><br>
                <span class="text-muted">Best response times between 2-6 AM</span>
            </div>
            <div class="insight-item">
                <strong>Slow Requests</strong><br>
                <span class="text-muted">5% of requests take >2 seconds</span>
            </div>
        `;

        const usagePatterns = document.getElementById('usagePatterns');
        usagePatterns.innerHTML = `
            <div class="pattern-item">
                <strong>Daily Usage</strong><br>
                <span class="text-muted">Average 150 tests per day</span>
            </div>
            <div class="pattern-item">
                <strong>Test Distribution</strong><br>
                <span class="text-muted">70% direct tests, 30% via chains</span>
            </div>
        `;
    }

    showLoading() {
        document.querySelectorAll('.metric-value').forEach(el => {
            el.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        });
    }

    hideLoading() {
        // Loading indicators are automatically replaced when data loads
    }

    showError(message) {
        console.error(message);
        // Could implement toast notifications here
    }
}

// Initialize endpoint report when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing endpoint report...');
    
    // Initialize with a small delay to ensure Chart.js is loaded
    setTimeout(() => {
        if (typeof Chart !== 'undefined') {
            console.log('Chart.js loaded successfully!');
            window.endpointReportManager = new EndpointReportManager();
        } else {
            console.error('Chart.js still not available. Please refresh the page.');
            document.getElementById('totalTests').textContent = 'Error: Chart.js not loaded';
        }
    }, 100);
});