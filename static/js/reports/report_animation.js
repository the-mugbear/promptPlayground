// Enhanced JavaScript for cyberpunk theme functionality
document.addEventListener('DOMContentLoaded', function() {
    // Get theme colors for consistent styling
    const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text-color').trim() || '#ffffff';
    const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent-color').trim() || '#00ff41';
    const secondaryColor = getComputedStyle(document.documentElement).getPropertyValue('--secondary-color').trim() || '#ff00aa';
    
    // We'll hook into the existing chart rendering system instead of replacing it
    
    // Override Chart.js defaults for cyberpunk styling
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = textColor;
        Chart.defaults.font.family = "'Press Start 2P', monospace, sans-serif";
        
        // Store the original renderOverallMetricsChart function
        const originalRenderOverallMetricsChart = window.renderOverallMetricsChart;
        // Override the function to apply cyberpunk styling
        window.renderOverallMetricsChart = function(metrics, canvasElement) {
            if (!canvasElement || typeof Chart === 'undefined') return;
            
            const ctx = canvasElement.getContext('2d');
            const chartData = {
                labels: ['Passed', 'Failed', 'Skipped', 'Pending Review'],
                datasets: [{
                    label: 'Overall Test Run Statuses',
                    data: [metrics.passed, metrics.failed, metrics.skipped, metrics.pending_review],
                    backgroundColor: [
                        'rgba(0, 255, 65, 0.8)',    // Neon green for passed
                        'rgba(255, 0, 170, 0.8)',   // Neon pink for failed
                        'rgba(255, 206, 86, 0.8)',  // Neon yellow for skipped
                        'rgba(0, 255, 255, 0.8)'    // Cyan for pending
                    ],
                    borderColor: [
                        'rgba(0, 255, 65, 1)',
                        'rgba(255, 0, 170, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(0, 255, 255, 1)'
                    ],
                    borderWidth: 2
                }]
            };
            
            if (chartInstances.overall) chartInstances.overall.destroy();
            chartInstances.overall = new Chart(ctx, {
                type: 'pie',
                data: chartData,
                options: createCyberpunkChartOptions()
            });
        };
        
        // Store the original renderFailedTransformationsChart function
        const originalRenderFailedTransformationsChart = window.renderFailedTransformationsChart;
        // Override the function to apply cyberpunk styling
        window.renderFailedTransformationsChart = function(transformationsData, canvasElement) {
            if (!canvasElement || typeof Chart === 'undefined' || Object.keys(transformationsData).length === 0) {
                return;
            }
            
            const ctx = canvasElement.getContext('2d');
            const labels = Object.keys(transformationsData);
            const dataValues = Object.values(transformationsData);
            
            const chartData = {
                labels: labels,
                datasets: [{
                    label: 'Count',
                    data: dataValues,
                    backgroundColor: 'rgba(255, 0, 170, 0.8)', // Neon pink
                    borderColor: 'rgba(255, 0, 170, 1)',
                    borderWidth: 2
                }]
            };
            
            if (chartInstances.transformations) chartInstances.transformations.destroy();
            chartInstances.transformations = new Chart(ctx, {
                type: 'bar',
                data: chartData,
                options: createCyberpunkChartOptions('bar')
            });
        };
        
        // Store the original renderPerRunChart function
        const originalRenderPerRunChart = window.renderPerRunChart;
        // Override the function to apply cyberpunk styling
        window.renderPerRunChart = function(metrics, canvasId) {
            const canvasElement = document.getElementById(canvasId);
            if (!canvasElement || typeof Chart === 'undefined' || metrics.total === 0) {
                if (canvasElement) canvasElement.parentElement.innerHTML = '<i>No executions for this run.</i>';
                return;
            }
            
            const ctx = canvasElement.getContext('2d');
            const chartData = {
                labels: ['Passed', 'Failed', 'Skipped', 'Pending'],
                datasets: [{
                    data: [metrics.passed, metrics.failed, metrics.skipped, metrics.pending_review],
                    backgroundColor: [
                        'rgba(0, 255, 65, 0.8)',    // Neon green
                        'rgba(255, 0, 170, 0.8)',   // Neon pink
                        'rgba(255, 206, 86, 0.8)',  // Neon yellow
                        'rgba(0, 255, 255, 0.8)'    // Cyan
                    ],
                    borderWidth: 2
                }]
            };
            
            if (chartInstances.runs[canvasId]) {
                chartInstances.runs[canvasId].destroy();
            }
            
            chartInstances.runs[canvasId] = new Chart(ctx, {
                type: 'doughnut',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: { 
                            enabled: true,
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: secondaryColor,
                            bodyColor: textColor,
                            borderColor: accentColor,
                            borderWidth: 1
                        }
                    }
                }
            });
        };
    }
    
    // Add CSS for cyberpunk effects
    addCyberpunkStyles();
    
    // Wait for the report details to load before adding cyberpunk effects
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.target.id === 'report-details') {
                // Apply cyberpunk effects to the newly loaded content
                addCyberpunkEffects();
            }
        });
    });
    
    // Start observing the report-details element
    observer.observe(document.getElementById('report-details'), { childList: true, subtree: true });
    
    // Helper function to create cyberpunk chart options
    function createCyberpunkChartOptions(type = 'pie') {
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: textColor,
                        font: {
                            family: "'Press Start 2P', monospace",
                            size: 10
                        },
                        padding: 15
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: secondaryColor,
                    bodyColor: textColor,
                    borderColor: accentColor,
                    borderWidth: 1,
                    padding: 10,
                    titleFont: {
                        family: "'Press Start 2P', monospace",
                        size: 12
                    },
                    bodyFont: {
                        family: "'Press Start 2P', monospace",
                        size: 10
                    },
                    displayColors: true
                }
            }
        };
        
        // Add scales for bar/line charts
        if (type !== 'pie' && type !== 'doughnut') {
            options.scales = {
                x: {
                    grid: {
                        color: 'rgba(0, 255, 65, 0.1)',
                        borderColor: secondaryColor
                    },
                    ticks: {
                        color: textColor,
                        font: {
                            family: "'Press Start 2P', monospace",
                            size: 8
                        }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(0, 255, 65, 0.1)',
                        borderColor: secondaryColor
                    },
                    ticks: {
                        color: textColor,
                        font: {
                            family: "'Press Start 2P', monospace",
                            size: 8
                        }
                    }
                }
            };
        }
        
        return options;
    }
    
    // Add cyberpunk-specific styles to the page
    function addCyberpunkStyles() {
        const styleElement = document.createElement('style');
        styleElement.id = 'cyberpunk-styles';
        styleElement.textContent = `
            @keyframes textFlicker {
                0% { opacity: 1; }
                92% { opacity: 1; }
                93% { opacity: 0.6; }
                94% { opacity: 1; }
                97% { opacity: 1; }
                98% { opacity: 0.4; }
                99% { opacity: 1; }
                99.5% { opacity: 0.7; }
                100% { opacity: 1; }
            }
            
            @keyframes scanline {
                0% { transform: translateY(-100%); }
                100% { transform: translateY(1000%); } 
            }
            
            .cyberpunk-flicker {
                animation: textFlicker 6s infinite;
            }
            
            .report-loading {
                color: ${accentColor};
                position: relative;
                padding-left: 20px;
            }
            
            .report-loading:before {
                content: '';
                position: absolute;
                left: 0;
                top: 50%;
                width: 10px;
                height: 10px;
                margin-top: -5px;
                background-color: ${accentColor};
                animation: blink 1s infinite;
            }
            
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0; }
            }
            
            .content-card {
                border: 2px solid ${accentColor};
                box-shadow: 0 0 10px ${accentColor}, inset 0 0 5px ${accentColor};
                position: relative;
                overflow: hidden;
            }
            
            .content-card:after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: ${accentColor};
                box-shadow: 0 0 20px 3px ${accentColor};
                opacity: 0.6;
            }
            
            .chart-container h3 {
                color: ${secondaryColor};
                text-shadow: 0 0 5px ${secondaryColor}, 0 0 10px ${secondaryColor};
                margin-bottom: 15px;
            }
            
            .test-run-item {
                border: 1px solid ${secondaryColor};
                margin-bottom: 10px;
                padding: 10px;
                background-color: rgba(0, 0, 0, 0.3);
                position: relative;
                overflow: hidden;
            }
            
            .test-run-item:after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, transparent 98%, ${accentColor});
                pointer-events: none;
            }
            
            .status-passed, .status-success {
                color: rgba(0, 255, 65, 1);
                text-shadow: 0 0 5px rgba(0, 255, 65, 0.5);
            }
            
            .status-failed, .status-failure {
                color: rgba(255, 0, 170, 1);
                text-shadow: 0 0 5px rgba(255, 0, 170, 0.5);
            }
            
            .status-skipped {
                color: rgba(255, 206, 86, 1);
                text-shadow: 0 0 5px rgba(255, 206, 86, 0.5);
            }
            
            .status-pending_review {
                color: rgba(0, 255, 255, 1);
                text-shadow: 0 0 5px rgba(0, 255, 255, 0.5);
            }
            
            select {
                background-color: #000;
                color: ${textColor};
                border: 1px solid ${accentColor};
                padding: 5px;
                box-shadow: 0 0 5px ${accentColor};
                transition: all 0.3s ease;
            }
            
            select:focus {
                box-shadow: 0 0 15px ${accentColor};
                outline: none;
            }
            
            .report-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            
            @media (max-width: 768px) {
                .report-grid {
                    grid-template-columns: 1fr;
                }
            }
            /* New Layout Styles */
            .report-container {
                display: flex;
                flex-direction: column;
                gap: 30px;
            }
            
            .charts-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 10px;
            }
            
            .chart-container {
                border: 1px solid ${accentColor};
                padding: 15px;
                background-color: rgba(0, 0, 0, 0.3);
                box-shadow: 0 0 8px rgba(0, 255, 65, 0.2);
                transition: box-shadow 0.3s ease;
            }
            
            .chart-container:hover {
                box-shadow: 0 0 12px ${accentColor};
            }
            
            .test-runs-section {
                border: 1px solid ${secondaryColor};
                padding: 15px;
                background-color: rgba(0, 0, 0, 0.2);
            }
            
            .test-runs-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            
            .test-run-item {
                border: 1px solid ${secondaryColor};
                margin-bottom: 0;
                position: relative;
                overflow: hidden;
            }
            
            .run-content {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 10px;
            }
            
            .per-run-metrics {
                flex: 2;
            }
            
            .per-run-chart-container {
                flex: 1;
                max-width: 100px;
                margin: 0;
            }
            
            .dialogues-list {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 10px;
            }
            
            .dialogues-list li {
                border: 1px solid ${accentColor};
                padding: 8px;
                background-color: rgba(0, 0, 0, 0.3);
                transition: background-color 0.2s;
            }
            
            .dialogues-list li:hover {
                background-color: rgba(0, 255, 65, 0.1);
            }
            
            .report-section {
                border: 1px solid ${accentColor};
                padding: 15px;
                background-color: rgba(0, 0, 0, 0.2);
                margin-top: 15px;
            }
            
            /* Responsive adjustments */
            @media (max-width: 768px) {
                .charts-row {
                    grid-template-columns: 1fr;
                }
                
                .test-runs-grid {
                    grid-template-columns: 1fr;
                }
                
                .dialogues-list {
                    grid-template-columns: 1fr;
                }
            }
        `;
        document.head.appendChild(styleElement);
    }
    
    // Add cyberpunk decorative effects to the page
    function addCyberpunkEffects() {
        // Add decorative elements to chart containers
        document.querySelectorAll('.chart-container, [id$="-chart-dynamic-container"]').forEach(container => {
            // Skip if already enhanced
            if (container.classList.contains('cyberpunk-enhanced')) return;
            container.classList.add('cyberpunk-enhanced');
            
            // Add scanline effect
            const scanline = document.createElement('div');
            scanline.classList.add('cyberpunk-scanline');
            scanline.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 2px;
                background-color: ${secondaryColor};
                opacity: 0.5;
                z-index: 1;
                pointer-events: none;
                animation: scanline 2s linear infinite;
            `;
            container.style.position = 'relative';
            container.style.overflow = 'hidden';
            container.appendChild(scanline);
            
            // Add flickering effect to headings
            const headings = container.querySelectorAll('h3');
            headings.forEach(heading => {
                if (!heading.classList.contains('cyberpunk-flicker')) {
                    heading.classList.add('cyberpunk-flicker');
                }
            });
        });
        
        // Make test run items more cyberpunk
        document.querySelectorAll('.test-run-item').forEach(item => {
            if (item.classList.contains('cyberpunk-enhanced')) return;
            item.classList.add('cyberpunk-enhanced');
            
            // Add a subtle corner effect
            const corner = document.createElement('div');
            corner.style.cssText = `
                position: absolute;
                top: 0;
                right: 0;
                width: 20px;
                height: 20px;
                background: linear-gradient(135deg, transparent 40%, ${accentColor} 60%, transparent 90%);
                z-index: 1;
            `;
            item.style.position = 'relative';
            item.appendChild(corner);
        });
        
        // Add decorative border to the entire report
        const reportDetails = document.getElementById('report-details');
        if (reportDetails && !reportDetails.classList.contains('cyberpunk-enhanced')) {
            reportDetails.classList.add('cyberpunk-enhanced');
            reportDetails.style.cssText += `
                border: 1px solid ${accentColor};
                box-shadow: 0 0 10px rgba(0, 255, 65, 0.3);
                padding: 20px;
                position: relative;
                overflow: hidden;
            `;
            
            // Add a "circuit board" background decoration
            const circuitDecoration = document.createElement('div');
            circuitDecoration.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: 
                    radial-gradient(circle at 10% 20%, transparent 1px, ${accentColor} 1px, ${accentColor} 2px, transparent 2px) 40px 30px / 60px 60px,
                    linear-gradient(to right, transparent 98%, ${secondaryColor} 98%, ${secondaryColor} 100%, transparent 100%) 0 0 / 200px 100%;
                opacity: 0.05;
                pointer-events: none;
                z-index: -1;
            `;
            reportDetails.appendChild(circuitDecoration);
        }
    }
    
    // Initial enhancement
    addCyberpunkEffects();
});