document.addEventListener('DOMContentLoaded', function() {
    // Overall donut chart
    var overallCanvas = document.getElementById('cumulativeStatusChart');
    if (overallCanvas) {
        var passed = parseInt(overallCanvas.getAttribute('data-passed'));
        var failed = parseInt(overallCanvas.getAttribute('data-failed'));
        var skipped = parseInt(overallCanvas.getAttribute('data-skipped'));
        var pending = parseInt(overallCanvas.getAttribute('data-pending'));
        
        var ctxOverall = overallCanvas.getContext('2d');
        new Chart(ctxOverall, {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Skipped', 'Pending Review'],
                datasets: [{
                    data: [passed, failed, skipped, pending],
                    backgroundColor: ['#34D399', '#F87171', '#D1D5DB', '#FBBF24']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
  
    // Per-attempt donut charts (smaller)
    var attemptCanvases = document.querySelectorAll('canvas[id^="attemptDonut-"]');
    attemptCanvases.forEach(function(canvas) {
        // Set a smaller fixed size for these attempt donuts
        canvas.style.width = "150px";
        canvas.style.height = "150px";
        // Alternatively, you can set canvas.width and canvas.height
        canvas.width = 150;
        canvas.height = 150;
        
        var passed = parseInt(canvas.getAttribute('data-passed'));
        var failed = parseInt(canvas.getAttribute('data-failed'));
        var skipped = parseInt(canvas.getAttribute('data-skipped'));
        var pending = parseInt(canvas.getAttribute('data-pending'));
        
        var ctx = canvas.getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Skipped', 'Pending Review'],
                datasets: [{
                    data: [passed, failed, skipped, pending],
                    backgroundColor: ['#34D399', '#F87171', '#D1D5DB', '#FBBF24']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false  // Hide legend for the small charts
                    }
                }
            }
        });
    });
  });
  