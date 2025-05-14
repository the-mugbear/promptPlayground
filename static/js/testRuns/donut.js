// static/js/testRuns/donut.js
(function() {
  // Grab the <canvas> once
  const canvas = document.getElementById('cumulativeStatusChart');
  if (!canvas) return;  // nothing to do if the canvas isn’t in this view

  // Parse out your four counters
  const values = [
    parseInt(canvas.dataset.passed,  10),
    parseInt(canvas.dataset.failed,  10),
    parseInt(canvas.dataset.skipped, 10),
    parseInt(canvas.dataset.pending, 10),
  ];
  const total = values.reduce((sum, v) => sum + v, 0);

  // If there’s literally no data yet, draw a single grey “No data” slice
  if (total === 0) {
    console.log('🍩 Donut: no data yet, drawing placeholder');
    window.cumulativeChart = new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['No data'],
        datasets: [{
          data: [1],
          backgroundColor: ['#444']
        }],
      },
      options: {
        cutout: '50%',
        plugins: { legend: { display: false } },
        layout: { padding: 10 }
      }
    });
    return;
  }

  // Otherwise draw the real neon‐green donut
  console.log('🍩 Initializing donut chart with real data…');
  window.cumulativeChart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Passed','Failed','Skipped','Pending Review'],
      datasets: [{
        data: values,
        backgroundColor: ['#00FF41','#FF00AA','#FFFF00','#00FFFF']
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '50%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#00FF41' }
        },
        tooltip: {
          backgroundColor: '#111',
          titleColor: '#00FF41',
          bodyColor: '#00FF41'
        }
      },
      layout: { padding: 10 }
    }
  });
})();
