/**
 * Vue 3 Application for Cyber-Lighthouse Dashboard
 * Enhanced with all UI improvements
 */

const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

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
    const filterTag = ref("");
    const filterSeverity = ref("");
    const alertsOffset = ref(0);
    const alertsLimit = ref(20);
    const alertsPage = ref(1);
    const alertsTotalCount = ref(0);
    const hasMoreAlerts = ref(true);
    const filterStats = ref(null);
    const trendingTags = ref({});
    const bookmarks = ref([]);
    const showBookmarksOnly = ref(false);
    const lastRefreshTime = ref(null);
    const newAlertsCount = ref(0);
    const previousAlertCount = ref(0);
    const toastMessages = ref([]);
    const theme = ref(localStorage.getItem("theme") || "dark");

    // History pagination
    const historyPage = ref(1);
    const historyPageSize = ref(50);
    const historyDateFrom = ref("");
    const historyDateTo = ref("");
    const historyTotalCount = ref(0);

    // Reports
    const expandedReports = ref(new Set());
    const reportsWithTOC = ref({});

    // Alerts collapse
    const expandedAlerts = ref(new Set());
    const collapseOldAlerts = ref(true);

    // Keyboard shortcuts modal
    const showShortcutsModal = ref(false);

    // Export dropdown
    const showExportMenu = ref(false);

    // Mobile menu
    const showMobileMenu = ref(false);

    // Background task status
    const taskStatus = ref(null);
    const taskTriggerLoading = ref(false);

    // Charts
    let chartBySource = null;
    let chartByDate = null;

    // Toast notification system
    const showToast = (message, type = "info", duration = 3000) => {
      const id = Date.now();
      toastMessages.value.push({ id, message, type });
      setTimeout(() => {
        toastMessages.value = toastMessages.value.filter(t => t.id !== id);
      }, duration);
    };

    // Severity colors
    const getSeverityColor = (severity) => {
      const colors = {
        critical: "red",
        high: "orange",
        medium: "yellow",
        low: "green"
      };
      return colors[severity] || "yellow";
    };

    const getSeverityIcon = (severity) => {
      const icons = {
        critical: "fa-radiation",
        high: "fa-exclamation-triangle",
        medium: "fa-exclamation-circle",
        low: "fa-info-circle"
      };
      return icons[severity] || "fa-info-circle";
    };

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

      if (filterTag.value) {
        filtered = filtered.filter((a) => 
          a.tags && a.tags.some(tag => tag.toLowerCase().includes(filterTag.value.toLowerCase()))
        );
      }

      return filtered;
    });

    const paginatedHistory = computed(() => {
      const start = (historyPage.value - 1) * historyPageSize.value;
      const end = start + historyPageSize.value;
      return filteredArticles.value.slice(start, end);
    });

    const totalHistoryPages = computed(() => {
      return Math.ceil(filteredArticles.value.length / historyPageSize.value);
    });

    const alertsCount = computed(() => alerts.value.length);
    const reportsCount = computed(() => reports.value.length);
    const bookmarksCount = computed(() => bookmarks.value.length);

    // Alerts pagination
    const alertsTotalPages = computed(() => Math.ceil(alertsTotalCount.value / alertsLimit.value) || 1);
    const alertsPageStart = computed(() => (alertsPage.value - 1) * alertsLimit.value + 1);
    const alertsPageEnd = computed(() => Math.min(alertsPage.value * alertsLimit.value, alertsTotalCount.value));

    const filteredAlerts = computed(() => {
      if (!filterSeverity.value) {
        return alerts.value;
      }
      return alerts.value.filter(alert => 
        alert.severity === filterSeverity.value
      );
    });

    const getFilteredCount = (severity) => {
      return alerts.value.filter(alert => alert.severity === severity).length;
    };

    const getSeverityCount = (severity) => {
      return alerts.value.filter(alert => alert.severity === severity).length;
    };

    const getSeverityPercentage = (severity) => {
      const count = alerts.value.filter(alert => alert.severity === severity).length;
      return alerts.value.length > 0 ? (count / alerts.value.length * 100) : 0;
    };

    const getThreatLevel = () => {
      const critical = getSeverityCount('critical');
      const high = getSeverityCount('high');
      const total = alerts.value.length;
      
      if (total === 0) return 'None';
      if (critical > 5 || (critical / total > 0.3)) return 'Elevated';
      if (critical > 2 || high > 5) return 'High';
      if (critical > 0 || high > 2) return 'Moderate';
      return 'Low';
    };

    const getThreatLevelColor = () => {
      const level = getThreatLevel();
      const colors = {
        'Elevated': 'text-red-400',
        'High': 'text-orange-400',
        'Moderate': 'text-yellow-400',
        'Low': 'text-green-400',
        'None': 'text-slate-400'
      };
      return colors[level] || 'text-slate-400';
    };

    const getThreatLevelIcon = () => {
      const level = getThreatLevel();
      const icons = {
        'Elevated': 'fa-radiation',
        'High': 'fa-exclamation-triangle',
        'Moderate': 'fa-exclamation-circle',
        'Low': 'fa-shield-alt',
        'None': 'fa-check-circle'
      };
      return icons[level] || 'fa-question-circle';
    };

    const isAlertOld = (alertDate) => {
      if (!collapseOldAlerts.value) return false;
      const alertTime = new Date(alertDate).getTime();
      const now = Date.now();
      return (now - alertTime) > 24 * 60 * 60 * 1000; // 24 hours
    };

    const isReportExpanded = (index) => expandedReports.value.has(index);
    
    const toggleReportExpand = (index) => {
      const newSet = new Set(expandedReports.value);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      expandedReports.value = newSet;
    };

    const isAlertExpanded = (index) => expandedAlerts.value.has(index);
    
    const toggleAlertExpand = (index) => {
      const newSet = new Set(expandedAlerts.value);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      expandedAlerts.value = newSet;
    };

    const toggleTheme = () => {
      theme.value = theme.value === "dark" ? "light" : "dark";
      localStorage.setItem("theme", theme.value);
      document.documentElement.classList.toggle("light-theme", theme.value === "light");
    };

    // Deduplication function
    const deduplicateAlerts = (alertsList) => {
      const grouped = new Map();

      alertsList.forEach(alert => {
        const key = alert.title.substring(0, 50).toLowerCase().trim();

        if (!grouped.has(key)) {
          grouped.set(key, {
            ...alert,
            sources: [{ source: alert.source, link: alert.link }],
          });
        } else {
          const existing = grouped.get(key);
          if (!existing.sources.some(s => s.source === alert.source)) {
            existing.sources.push({ source: alert.source, link: alert.link });
          }
        }
      });

      return Array.from(grouped.values()).map(alert => ({
        ...alert,
        multiSource: alert.sources.length > 1,
        sourceLinks: alert.sources,
      }));
    };

    // Methods
    const refreshData = async (isAutoRefresh = false) => {
      isLoading.value = true;
      try {
        const offset = (alertsPage.value - 1) * alertsLimit.value;
        const [alertsData, reportsData, statsData, statusData, articlesData, bookmarksData] =
          await Promise.all([
            apiClient.getAlerts(alertsLimit.value, offset),
            apiClient.getReports(),
            apiClient.getStatistics(),
            apiClient.getSystemStatus(),
            apiClient.searchArticles({ limit: 10000 }),
            apiClient.getBookmarks(),
          ]);

        const rawAlerts = alertsData.alerts || [];
        alerts.value = deduplicateAlerts(rawAlerts);
        alertsTotalCount.value = alertsData.total_count || 0;

        // Check for new alerts
        if (previousAlertCount.value > 0 && rawAlerts.length > previousAlertCount.value) {
          newAlertsCount.value = rawAlerts.length - previousAlertCount.value;
        }
        previousAlertCount.value = rawAlerts.length;

        filterStats.value = alertsData.filter_stats || null;
        trendingTags.value = alertsData.filter_stats?.trending_tags || {};

        reports.value = reportsData.reports || [];
        statistics.value = statsData;
        systemStatus.value = statusData;
        allArticles.value = articlesData.articles || [];
        historyTotalCount.value = articlesData.total_count || 0;
        bookmarks.value = bookmarksData || [];

        lastRefreshTime.value = new Date();
        updateCharts();

        if (!isAutoRefresh) {
          showToast("Data refreshed successfully", "success");
        }
      } catch (error) {
        console.error("Error refreshing data:", error);
        showToast("Error loading data. Please check server connection.", "error", 5000);
      } finally {
        isLoading.value = false;
      }
    };

    const fetchTaskStatus = async () => {
      try {
        taskStatus.value = await apiClient.getTaskStatus();
      } catch (error) {
        console.error("Error fetching task status:", error);
      }
    };

    const triggerTask = async (task) => {
      try {
        taskTriggerLoading.value = true;
        const result = await apiClient.triggerTask(task);
        showToast(result.message || `${task} triggered`, "success");
        // Refresh task status after trigger
        setTimeout(() => fetchTaskStatus(), 2000);
      } catch (error) {
        console.error("Error triggering task:", error);
        showToast("Failed to trigger task", "error");
      } finally {
        taskTriggerLoading.value = false;
      }
    };

    const formatTimeAgo = (isoDate) => {
      if (!isoDate) return "Never";
      const now = new Date();
      const date = new Date(isoDate);
      const diff = Math.floor((now - date) / 1000);

      if (diff < 60) return "just now";
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      return `${Math.floor(diff / 86400)}d ago`;
    };

    const changeAlertsPage = async (newPage) => {
      if (newPage < 1) return;
      const totalPages = Math.ceil(alertsTotalCount.value / alertsLimit.value) || 1;
      if (newPage > totalPages) return;

      alertsPage.value = newPage;
      await refreshData(false);

      // Scroll to top of alerts section
      const alertsSection = document.querySelector('[v-show*="alerts"]');
      if (alertsSection) {
        alertsSection.scrollIntoView({ behavior: 'smooth' });
      }
    };

    const changeHistoryPage = (page) => {
      historyPage.value = page;
    };

    const applyHistoryFilters = () => {
      historyPage.value = 1;
    };

    const toggleBookmark = async (alert) => {
      try {
        const result = await apiClient.toggleBookmark(
          alert.id,
          {
            title: alert.title,
            source: alert.source,
            date: alert.date,
            link: alert.link,
            severity: alert.severity || "medium"
          }
        );
        
        if (result.bookmarked) {
          showToast("Alert bookmarked", "success");
        } else {
          showToast("Bookmark removed", "info");
        }
        
        // Refresh bookmarks
        bookmarks.value = await apiClient.getBookmarks();
      } catch (error) {
        showToast("Error toggling bookmark", "error");
      }
    };

    const isBookmarked = (alertId) => {
      return bookmarks.value.some(b => b.id === alertId);
    };

    const exportAlerts = async (format) => {
      try {
        const result = await apiClient.exportAlerts(format, 1000);
        downloadFile(result.content, result.filename, format === "csv" ? "text/csv" : "text/markdown");
        showToast(`Alerts exported to ${format.toUpperCase()}`, "success");
        showExportMenu.value = false;
      } catch (error) {
        showToast("Error exporting alerts", "error");
      }
    };

    const exportReport = async (index, format) => {
      try {
        const result = await apiClient.exportReport(index, format);
        if (result.error) {
          showToast(result.error, "error");
          return;
        }
        downloadFile(result.content, result.filename, "text/markdown");
        showToast("Report exported", "success");
      } catch (error) {
        showToast("Error exporting report", "error");
      }
    };

    const downloadFile = (content, filename, mimeType) => {
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    };

    const filterByTag = (tag) => {
      filterTag.value = filterTag.value === tag ? "" : tag;
      historyPage.value = 1;
      if (currentTab.value !== "articles") {
        currentTab.value = "articles";
      }
    };

    const filterBySeverity = (severity) => {
      filterSeverity.value = filterSeverity.value === severity ? "" : severity;
      if (currentTab.value !== "alerts") {
        currentTab.value = "alerts";
      }
    };

    const clearNotificationBadge = () => {
      newAlertsCount.value = 0;
    };

    const updateCharts = () => {
      if (chartBySource) chartBySource.destroy();
      if (chartByDate) chartByDate.destroy();

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
            datasets: [{
              data: counts,
              backgroundColor: ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40"],
              borderColor: "#fff",
              borderWidth: 2,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
              legend: { position: "bottom" },
              tooltip: {
                callbacks: {
                  label: function(context) {
                    const label = context.label || '';
                    const value = context.parsed || 0;
                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                    const percentage = ((value / total) * 100).toFixed(1);
                    return `${label}: ${value} (${percentage}%)`;
                  }
                }
              }
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
            datasets: [{
              label: "Articles",
              data: counts,
              backgroundColor: "#36A2EB",
              borderColor: "#2196F3",
              borderWidth: 1,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
              y: { beginAtZero: true, ticks: { stepSize: 1 } },
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  title: function(items) {
                    return `Date: ${items[0].label}`;
                  },
                  label: function(context) {
                    return `${context.parsed.y} articles`;
                  }
                }
              }
            },
          },
        });
      }
    };

    const autoRefresh = () => {
      setInterval(() => {
        if (document.hidden) return;
        refreshData(true);
      }, 30000);
    };

    // Keyboard shortcuts
    const handleKeyboard = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") {
        return;
      }

      if (e.key === "?") {
        e.preventDefault();
        showShortcutsModal.value = !showShortcutsModal.value;
      } else if (e.key >= "1" && e.key <= "4") {
        const tabs = ["alerts", "reports", "stats", "articles"];
        currentTab.value = tabs[parseInt(e.key) - 1];
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        refreshData();
      } else if (e.key === "/") {
        e.preventDefault();
        const searchInput = document.querySelector('input[placeholder*="Search"]');
        if (searchInput) searchInput.focus();
      }
    };

    // Markdown renderer
    const renderMarkdown = (content) => {
      if (!content) return "";

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

      let html = escapeHtml(content);
      html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
      html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
      html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
      html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
      html = html.replace(/\n/g, '<br>');

      return html;
    };

    const renderReport = (content) => {
      if (!content) return "";

      // Escape HTML first
      let html = content
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      
      // Headers (process in order to avoid conflicts)
      html = html.replace(/^# (.*$)/gm, '<h1>$1</h1>');
      html = html.replace(/^## (.*$)/gm, '<h2>$1</h2>');
      html = html.replace(/^### (.*$)/gm, '<h3>$1</h3>');
      html = html.replace(/^#### (.*$)/gm, '<h4>$1</h4>');
      
      // Bold (before italic to avoid conflicts)
      html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      
      // Italic
      html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
      
      // Inline code
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
      
      // Horizontal rules
      html = html.replace(/^---$/gm, '<hr>');
      html = html.replace(/^\*\*\*$/gm, '<hr>');
      
      // Process lists with proper nesting based on indentation
      const lines = html.split('\n');
      const result = [];
      let listItems = [];
      
      const closeList = () => {
        if (listItems.length === 0) return;
        
        // Find base indentation (minimum)
        const baseIndent = Math.min(...listItems.map(item => item.indent));
        
        // Build nested HTML structure
        const buildNestedList = (items, parentIndent) => {
          let html = '<ul>';
          let i = 0;
          
          while (i < items.length) {
            const item = items[i];
            
            if (item.indent === parentIndent) {
              // Same level - regular list item
              html += `<li>${item.content}</li>`;
              i++;
            } else if (item.indent > parentIndent) {
              // Deeper level - nested list
              const nestedItems = [];
              while (i < items.length && items[i].indent > parentIndent) {
                nestedItems.push(items[i]);
                i++;
              }
              html += buildNestedList(nestedItems, nestedItems[0].indent);
            } else {
              // Shouldn't happen if called correctly
              break;
            }
          }
          
          html += '</ul>';
          return html;
        };
        
        result.push(buildNestedList(listItems, baseIndent));
        listItems = [];
      };
      
      for (const line of lines) {
        // Empty line - close current list
        if (!line.trim()) {
          closeList();
          result.push('');
          continue;
        }
        
        // Skip lines that are already HTML headers
        if (line.match(/^<(h[1-6])/)) {
          closeList();
          result.push(line);
          continue;
        }
        
        // Detect list items: optional whitespace + "- " + content
        const match = line.match(/^(\s*)- (.+)$/);
        if (match) {
          const indent = match[1].length;
          const content = match[2];
          listItems.push({ indent, content });
        } else {
          // Not a list item - wrap in paragraph
          closeList();
          result.push(`<p>${line}</p>`);
        }
      }
      
      // Close any remaining list
      closeList();
      
      html = result.join('\n');
      
      // Clean up multiple empty lines
      html = html.replace(/\n{3,}/g, '\n\n');
      
      return html;
    };

    const renderAlertAnalysis = (content) => {
      if (!content) return "";

      // Check if content has ALERT/IMPACT/TAGS format
      const hasStructuredFormat = content.includes('🚨') && content.includes('💥');

      if (hasStructuredFormat) {
        // Parse alert format: 🚨 ALERT, 💥 IMPACT, 🏷️ TAGS
        let html = escapeHtml(content);

        // Format ALERT section
        html = html.replace(/🚨\s*\*\*ALERT\*\*:\s*/g, '<div class="mb-3"><div class="flex items-start gap-2 mb-1"><span class="text-red-400 font-bold text-xs uppercase tracking-wide flex-shrink-0">🚨 Alert</span></div><p class="text-slate-200 leading-relaxed">');

        // Format IMPACT section  
        html = html.replace(/\n💥\s*\*\*IMPACT\*\*:\s*/g, '</p></div><div class="mb-3 pt-3 border-t border-slate-700/50"><div class="flex items-start gap-2 mb-1"><span class="text-orange-400 font-bold text-xs uppercase tracking-wide flex-shrink-0">💥 Impact</span></div><p class="text-slate-300 leading-relaxed">');

        // Remove TAGS section entirely (tags are shown in header)
        html = html.replace(/\n🏷️\s*\*\*TAGS\*\*:\s*.+$/gm, '');

        // Close any unclosed div tags
        html = html.replace(/<\/p><\/div>$/g, '</p></div>');
        html = html.replace(/<\/p>$/, '</p>');

        return html;
      }

      // Fall back to regular markdown rendering
      return renderMarkdown(content);
    };

    const escapeHtml = (text) => {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    };

    const formatTimestamp = (timestamp) => {
      if (!timestamp) return "Never";
      const date = new Date(timestamp);
      return date.toLocaleTimeString();
    };

    const generateReportAnchors = (content) => {
      return content.replace(/^(#{1,6})\s+(.+)$/gm, (match, hashes, text) => {
        const level = hashes.length;
        const cleanText = text.replace(/[^\w\s-]/g, '').trim();
        const anchor = cleanText.toLowerCase().replace(/\s+/g, '-');
        return `<h${level} id="${anchor}">${text}</h${level}>`;
      });
    };

    // Watchers
    watch(alertsOffset, () => {
      refreshData();
    });

    watch(filterTag, () => {
      historyPage.value = 1;
    });

    watch(filterSeverity, () => {
      // Reset to show first page when filter changes
      alertsOffset.value = 0;
    });

    // Lifecycle
    onMounted(() => {
      refreshData();
      fetchTaskStatus();
      autoRefresh();
      document.addEventListener("keydown", handleKeyboard);

      // Poll task status every 60s
      setInterval(() => fetchTaskStatus(), 60000);

      // Apply saved theme
      if (theme.value === "light") {
        document.documentElement.classList.add("light-theme");
      }

      // Expose filterByTag globally for onclick handlers in rendered HTML
      window.filterByTag = filterByTag;
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
      filterTag,
      filterSeverity,
      alertsOffset,
      alertsPage,
      alertsTotalCount,
      alertsTotalPages,
      alertsPageStart,
      alertsPageEnd,
      filterStats,
      trendingTags,
      bookmarks,
      showBookmarksOnly,
      lastRefreshTime,
      newAlertsCount,
      toastMessages,
      theme,
      historyPage,
      historyPageSize,
      historyDateFrom,
      historyDateTo,
      historyTotalCount,
      expandedReports,
      reportsWithTOC,
      expandedAlerts,
      collapseOldAlerts,
      showShortcutsModal,
      showExportMenu,
      showMobileMenu,
      taskStatus,
      taskTriggerLoading,
      uniqueSources,
      filteredArticles,
      paginatedHistory,
      totalHistoryPages,
      alertsCount,
      reportsCount,
      bookmarksCount,
      filteredAlerts,
      hasMoreAlerts,
      refreshData,
      fetchTaskStatus,
      triggerTask,
      formatTimeAgo,
      changeAlertsPage,
      changeHistoryPage,
      applyHistoryFilters,
      toggleBookmark,
      isBookmarked,
      exportAlerts,
      exportReport,
      filterByTag,
      filterBySeverity,
      clearNotificationBadge,
      updateCharts,
      renderMarkdown,
      renderReport,
      renderAlertAnalysis,
      formatTimestamp,
      generateReportAnchors,
      getSeverityColor,
      getSeverityIcon,
      getFilteredCount,
      getSeverityCount,
      getSeverityPercentage,
      getThreatLevel,
      getThreatLevelColor,
      getThreatLevelIcon,
      isAlertOld,
      isReportExpanded,
      toggleReportExpand,
      isAlertExpanded,
      toggleAlertExpand,
      toggleTheme,
      showToast,
    };
  },
});

// Mount app
app.mount("#app");
