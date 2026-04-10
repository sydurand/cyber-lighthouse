/**
 * API Client for Cyber-Lighthouse Dashboard
 */

class APIClient {
  constructor(baseURL = "/api") {
    this.baseURL = baseURL;
  }

  /**
   * Generic fetch wrapper with error handling
   */
  async fetch(endpoint, options = {}) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error: ${endpoint}`, error);
      throw error;
    }
  }

  /**
   * Get latest alerts
   */
  async getAlerts(limit = 20, offset = 0) {
    return this.fetch(`/alerts?limit=${limit}&offset=${offset}`);
  }

  /**
   * Get synthesis reports
   */
  async getReports(limit = 10, days = 7) {
    return this.fetch(`/reports?limit=${limit}&days=${days}`);
  }

  /**
   * Get report with table of contents
   */
  async getReportWithTOC(index) {
    return this.fetch(`/reports/${index}/toc`);
  }

  /**
   * Get statistics
   */
  async getStatistics() {
    return this.fetch("/stats");
  }

  /**
   * Search and filter articles
   */
  async searchArticles(options = {}) {
    const params = new URLSearchParams({
      limit: options.limit || 20,
      offset: options.offset || 0,
      ...(options.search && { search: options.search }),
      ...(options.source && { source: options.source }),
      ...(options.tag && { tag: options.tag }),
      ...(options.date_from && { date_from: options.date_from }),
      ...(options.date_to && { date_to: options.date_to }),
    });

    return this.fetch(`/articles?${params.toString()}`);
  }

  /**
   * Get system status
   */
  async getSystemStatus() {
    return this.fetch("/system");
  }

  /**
   * Re-analyze an alert with AI
   */
  async reanalyzeAlert(alertId) {
    return this.fetch(`/alerts/${alertId}/reanalyze`, { method: "POST" });
  }

  /**
   * Re-cluster all unclustered articles
   */
  async reclusterTopics() {
    return this.fetch("/topics/recluster", { method: "POST" });
  }

  /**
   * Get real-time progress of re-clustering operation
   */
  async getReclusterProgress() {
    return this.fetch("/topics/recluster/progress");
  }

  /**
   * Get all RSS feeds
   */
  async getRssFeeds() {
    return this.fetch("/settings/feeds");
  }

  /**
   * Add a new RSS feed
   */
  async addRssFeed(feed) {
    return this.fetch("/settings/feeds", {
      method: "POST",
      body: JSON.stringify(feed),
    });
  }

  /**
   * Update an RSS feed
   */
  async updateRssFeed(feedName, feed) {
    return this.fetch(`/settings/feeds/${encodeURIComponent(feedName)}`, {
      method: "PUT",
      body: JSON.stringify(feed),
    });
  }

  /**
   * Delete an RSS feed
   */
  async deleteRssFeed(feedName) {
    return this.fetch(`/settings/feeds/${encodeURIComponent(feedName)}`, {
      method: "DELETE",
    });
  }

  /**
   * Update all RSS feeds (bulk)
   */
  async updateRssFeeds(feeds) {
    return this.fetch("/settings/feeds", {
      method: "PUT",
      body: JSON.stringify({ feeds }),
    });
  }

  /**
   * Export alerts
   */
  async exportAlerts(format = "markdown", limit = 100) {
    return this.fetch(`/export/alerts?format=${format}&limit=${limit}`);
  }

  /**
   * Export report
   */
  async exportReport(index, format = "markdown") {
    return this.fetch(`/export/report/${index}?format=${format}`);
  }

  /**
   * Health check
   */
  async healthCheck() {
    return this.fetch("/health", { method: "GET" }).catch(() => {
      return { status: "offline" };
    });
  }

  /**
   * Get background task status
   */
  async getTaskStatus() {
    return this.fetch("/tasks");
  }

  /**
   * Trigger a background task manually
   */
  async triggerTask(task) {
    return this.fetch("/tasks/trigger", {
      method: "POST",
      body: JSON.stringify({ task }),
    });
  }

  /**
   * Get application version
   */
  async getVersion() {
    return this.fetch("/version");
  }
}

// Export for Vue
const apiClient = new APIClient();
