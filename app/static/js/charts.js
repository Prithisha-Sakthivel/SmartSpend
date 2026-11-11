document.addEventListener('DOMContentLoaded', () => {
  if (!window.Chart) return;
  const charts = window.smartSpendCharts || {};
  const palette = ['#40205F', '#7041A6', '#9C79B8', '#C5AED6', '#DCCEE7', '#777080', '#B8ADB9'];
  const currency = value => `₹${(value / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  Chart.defaults.font.family = 'Inter, Arial, sans-serif';
  Chart.defaults.color = '#777080';

  function create(id, config) {
    const canvas = document.getElementById(id);
    if (canvas) new Chart(canvas, config);
  }
  function axisOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 650, easing: 'easeOutQuart' },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', padding: 16 } },
        tooltip: { animation: { duration: 160 }, backgroundColor: '#261C30', padding: 11, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${currency(ctx.raw)}` } }
      },
      scales: {
        y: { beginAtZero: true, ticks: { callback: value => `₹${(value / 100).toLocaleString('en-IN')}` }, grid: { color: '#eeeaf0' } },
        x: { grid: { display: false } }
      }
    };
  }
  function cashflowConfig(data, line = false) {
    const options = axisOptions();
    options.scales.y.stacked = !line;
    options.scales.x.stacked = !line;
    return {
      type: line ? 'line' : 'bar',
      data: { labels: data.labels, datasets: [
        { label: 'Income', data: data.income, backgroundColor: '#7041A6', borderColor: '#7041A6', borderRadius: line ? 0 : 3, tension: .32, pointRadius: line ? 2 : undefined },
        { label: 'Expenses', data: data.expenses, backgroundColor: '#C5AED6', borderColor: '#9C79B8', borderRadius: line ? 0 : 3, tension: .32, pointRadius: line ? 2 : undefined }
      ] }, options
    };
  }

  if (charts.dashboardCashflow?.labels?.length) create('dashboardCashflow', cashflowConfig(charts.dashboardCashflow));
  if (charts.insightsCategories?.labels?.length) {
    create('insightsCategories', {
      type: 'bar',
      data: { labels: charts.insightsCategories.labels, datasets: [{ label: 'Expenses', data: charts.insightsCategories.values, backgroundColor: charts.insightsCategories.labels.map((_, i) => palette[i % palette.length]), borderRadius: 3 }] },
      options: { ...axisOptions(), indexAxis: 'y', plugins: { ...axisOptions().plugins, legend: { display: false }, tooltip: { animation: { duration: 160 }, backgroundColor: '#261C30', callbacks: { label: ctx => ` ${currency(ctx.raw)}` } } }, scales: { x: { beginAtZero: true, ticks: { callback: value => `₹${(value / 100).toLocaleString('en-IN')}` }, grid: { color: '#eeeaf0' } }, y: { grid: { display: false } } } }
    });
  }
  if (charts.reportCategories?.labels?.length) {
    create('categoryChart', {
      type: 'doughnut',
      data: { labels: charts.reportCategories.labels, datasets: [{ data: charts.reportCategories.values, backgroundColor: charts.reportCategories.labels.map((_, i) => palette[i % palette.length]), borderWidth: 2, borderColor: '#fff', hoverOffset: 5 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '69%', animation: { duration: 650, easing: 'easeOutQuart', animateRotate: true, animateScale: true }, transitions: { active: { animation: { duration: 180 } } }, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', padding: 16 } }, tooltip: { animation: { duration: 160 }, backgroundColor: '#261C30', padding: 11, callbacks: { label: ctx => ` ${ctx.label}: ${currency(ctx.raw)}` } } } }
    });
  }
  if (charts.reportCashflow?.labels?.length) create('reportCashflow', cashflowConfig(charts.reportCashflow, true));
  if (charts.reportSavings?.labels?.length) {
    const options = axisOptions();
    options.plugins.legend.display = false;
    create('reportSavings', { type: 'line', data: { labels: charts.reportSavings.labels, datasets: [{ label: 'Saved', data: charts.reportSavings.values, borderColor: '#7041A6', backgroundColor: 'rgba(112,65,166,.12)', fill: true, tension: .32, pointRadius: 3, pointHoverRadius: 5 }] }, options });
  }
});
