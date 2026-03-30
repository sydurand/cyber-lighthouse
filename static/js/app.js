/**
 * Vue 3 Application for Cyber-Lighthouse Dashboard
 */

const { createApp, ref, computed, onMounted, watch } = Vue;

const app = createApp({
  setup() {
    // State
    const currentTab = ref("alerts");
    const isLoading = ref(false);
    const alerts = ref([]);
    const reports = ref([]);
    const statistics = ref(null);
    const systemStatus = ref(null);
    const allArticles = ref([]);
    const searchQuery = ref("");
    const filterSource = ref("");
    const alertsOffset = ref(0);

    // Charts
    let chartBySource = null;
    let chartByDate = null;

    // Computed
    const uniqueSources = computed(() => {
      const sources = new Set(allArticles.value.map((a) => a.source));
      return Array.from(sources).sort();
    });

    const filteredArticles = computed(() => {
      let filtered = allArticles.value;

      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase();
        filtered = filtered.filter(
          (a) =>
            a.title.toLowerCase().includes(query) ||
            a.content.toLowerCase().includes(query)
        );
      }

      if (filterSource.value) {
        filtered = filtered.filter((a) => a.source === filterSource.value);
      }

      return filtered;
    });

    // Deduplication function - groups similar alerts from multiple sources
    const deduplicateAlerts = (alertsList) => {
      const grouped = new Map();

      alertsList.forEach(alert => {
        // Create a key based on title similarity (first 50 chars)
        const key = alert.title.substring(0, 50).toLowerCase().trim();

        if (!grouped.has(key)) {
          grouped.set(key, {
            ...alert,
            sources: [{ source: alert.source, link: alert.link }],
          });
        } else {
          const existing = grouped.get(key);
          // Add source if not already present
          if (!existing.sources.some(s => s.source === alert.source)) {
            existing.sources.push({ source: alert.source, link: alert.link });
          }
        }
      });

      // Convert map to array and format
      return Array.from(grouped.values()).map(alert => ({
        ...alert,
        multiSource: alert.sources.length > 1,
        sourceLinks: alert.sources,
      }));
    };

    // Methods
    const refreshData = async () => {
      isLoading.value = true;
      try {
        // Parallel requests
        const [alertsData, reportsData, statsData, statusData, articlesData] =
          await Promise.all([
            apiClient.getAlerts(20, alertsOffset.value),
            apiClient.getReports(),
            apiClient.getStatistics(),
            apiClient.getSystemStatus(),
            apiClient.searchArticles({ limit: 1000 }),
          ]);

        // Deduplicate alerts by similar title
        const rawAlerts = alertsData.alerts || [];
        alerts.value = deduplicateAlerts(rawAlerts);

        reports.value = reportsData.reports || [];
        statistics.value = statsData;
        systemStatus.value = statusData;
        allArticles.value = articlesData.articles || [];

        // Update charts when stats change
        updateCharts();
      } catch (error) {
        console.error("Error refreshing data:", error);
        alert("Error loading data. Please check the server connection.");
      } finally {
        isLoading.value = false;
      }
    };

    const updateCharts = () => {
      // Destroy old charts
      if (chartBySource) {
        chartBySource.destroy();
      }
      if (chartByDate) {
        chartByDate.destroy();
      }

      if (!statistics.value) return;

      // Chart by Source
      const sourceCtx = document.getElementById("chartBySource");
      if (sourceCtx && statistics.value.articles_by_source) {
        const sources = Object.keys(statistics.value.articles_by_source);
        const counts = Object.values(statistics.value.articles_by_source);

        chartBySource = new Chart(sourceCtx, {
          type: "doughnut",
          data: {
            labels: sources,
            datasets: [
              {
                data: counts,
                backgroundColor: [
                  "#FF6384",
                  "#36A2EB",
                  "#FFCE56",
                  "#4BC0C0",
                  "#9966FF",
                  "#FF9F40",
                ],
                borderColor: "#fff",
                borderWidth: 2,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
              legend: {
                position: "bottom",
              },
            },
          },
        });
      }

      // Chart by Date
      const dateCtx = document.getElementById("chartByDate");
      if (dateCtx && statistics.value.articles_by_date) {
        const dates = Object.keys(statistics.value.articles_by_date).sort();
        const counts = dates.map((d) => statistics.value.articles_by_date[d]);

        chartByDate = new Chart(dateCtx, {
          type: "bar",
          data: {
            labels: dates,
            datasets: [
              {
                label: "Articles",
                data: counts,
                backgroundColor: "#36A2EB",
                borderColor: "#2196F3",
                borderWidth: 1,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
              y: {
                beginAtZero: true,
                ticks: {
                  stepSize: 1,
                },
              },
            },
            plugins: {
              legend: {
                display: false,
              },
            },
          },
        });
      }
    };

    const autoRefresh = () => {
      // Refresh every 30 seconds
      setInterval(() => {
        if (document.hidden) return; // Don't refresh if tab is not visible
        refreshData();
      }, 30000);
    };

    // Simple markdown-like renderer
    const renderMarkdown = (content) => {
      if (!content) return "";

      // Try to use markdown-it if available
      if (typeof window.markdownit === 'function') {
        try {
          const md = window.markdownit({
            html: true,
            linkify: true,
            breaks: true,
          });
          return md.render(content);
        } catch (e) {
          console.error('Error rendering markdown:', e);
        }
      }

      // Fallback: simple formatting
      let html = escapeHtml(content);

      // Convert bold **text** to <strong>
      html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

      // Convert italic *text* to <em>
      html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

      // Convert headers # to <h2>, ## to <h3>, etc
      html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
      html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
      html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');

      // Convert newlines to <br>
      html = html.replace(/\n/g, '<br>');

      return html;
    };

    const escapeHtml = (text) => {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    };

    // Watchers
    watch(alertsOffset, () => {
      refreshData();
    });

    // Lifecycle
    onMounted(() => {
      refreshData();
      autoRefresh();
    });

    return {
      currentTab,
      isLoading,
      alerts,
      reports,
      statistics,
      systemStatus,
      allArticles,
      searchQuery,
      filterSource,
      alertsOffset,
      uniqueSources,
      filteredArticles,
      refreshData,
      updateCharts,
      renderMarkdown,
    };
  },
});

// Mount app
app.mount("#app");
