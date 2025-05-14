// static/js/testRuns/donut.js
(function() {
  const overallCanvas = document.getElementById('cumulativeStatusChart');
  if (!overallCanvas) return;

  console.log('🍩 Initializing donut chart…');

  const passed  = parseInt(overallCanvas.dataset.passed, 10);
  const failed  = parseInt(overallCanvas.dataset.failed, 10);
  const skipped = parseInt(overallCanvas.dataset.skipped, 10);
  const pending = parseInt(overallCanvas.dataset.pending, 10);

  window.cumulativeChart = new Chart(
    overallCanvas.getContext('2d'),
    {
      type: 'doughnut',
      data: {
        labels: ['Passed','Failed','Skipped','Pending Review'],
        datasets: [{
          data: [passed, failed, skipped, pending],
          backgroundColor: [
            '#00FF41',
            '#FF00AA',
            '#FFFF00',
            '#00FFFF'
          ]
        }]
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
    }
  );
})(); 
