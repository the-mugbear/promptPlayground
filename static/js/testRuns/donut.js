document.addEventListener('DOMContentLoaded', function() {
    var overallCanvas = document.getElementById('cumulativeStatusChart');
    if (overallCanvas) {
      var passed  = parseInt(overallCanvas.getAttribute('data-passed'));
      var failed  = parseInt(overallCanvas.getAttribute('data-failed'));
      var skipped = parseInt(overallCanvas.getAttribute('data-skipped'));
      var pending = parseInt(overallCanvas.getAttribute('data-pending'));
  
      var ctxOverall = overallCanvas.getContext('2d');
      new Chart(ctxOverall, {
        type: 'doughnut',
        data: {
          labels: ['Passed', 'Failed', 'Skipped', 'Pending Review'],
          datasets: [{
            data: [passed, failed, skipped, pending],
            backgroundColor: [
              '#00FF41', // neon green for Passed
              '#FF00AA', // pink for Failed
              '#FFFF00', // bright yellow for Skipped
              '#00FFFF'  // bright cyan for Pending
            ],
            // Optionally add border or dash:
            // borderColor: '#111',
            // borderWidth: 1,
            // borderDash: [5,5],
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          cutout: '50%', // More 'donut' look instead of a full pie
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                color: '#00FF41'  // neon green text in the legend
              }
            },
            tooltip: {
              backgroundColor: '#111',  // dark tooltip background
              titleColor: '#00FF41',    // neon green for title text
              bodyColor: '#00FF41'      // neon green for body text
              // Optionally add borderColor, borderWidth, etc.
            }
          },
          // You can add some layout padding to keep the donut from touching edges
          layout: {
            padding: 10
          }
        }
      });
    }
  });
  