"""Pydantic models for API responses."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ArticleResponse(BaseModel):
    """Response model for articles."""

    id: int
    source: str
    title: str
    content: str
    link: str
    date: str
    analysis: Optional[str] = None
    processed_for_daily: bool
    severity: str = Field(default="medium", description="Alert severity level")

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    """Response model for alerts (latest articles with analysis)."""

    id: int
    source: str
    title: str
    link: str
    date: str
    analysis: Optional[str] = None
    tags: List[str] = Field(default_factory=list, description="Security tags extracted from alert")
    timestamp: datetime = Field(default_factory=datetime.now)
    severity: str = Field(default="medium", description="Alert severity level")

    class Config:
        from_attributes = True


class BookmarkResponse(BaseModel):
    """Response model for bookmarked alerts."""

    id: int
    title: str
    source: str
    date: str
    link: str
    severity: str
    bookmarked_at: datetime = Field(default_factory=datetime.now)


class ReportResponse(BaseModel):
    """Response model for synthesis reports."""

    id: Optional[int] = None
    report_content: str
    articles_count: int
    generated_date: str
    timestamp: datetime = Field(default_factory=datetime.now)
    report_id: str = Field(default="", description="Cache key for download")


class ReportTOCItem(BaseModel):
    """Table of contents item for reports."""

    level: int
    text: str
    anchor: str


class ReportWithTOC(BaseModel):
    """Report with generated table of contents."""

    report: ReportResponse
    table_of_contents: List[ReportTOCItem] = Field(default_factory=list)


class StatisticsResponse(BaseModel):
    """Response model for statistics."""

    total_articles: int
    articles_today: int
    articles_this_week: int
    sources_count: int
    articles_by_source: Dict[str, int]
    articles_by_date: Dict[str, int]
    processed_articles: int
    unprocessed_articles: int
    cache_hit_rate: float = Field(description="Percentage of API calls saved by cache")
    api_calls_made: int
    api_calls_saved: int


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""

    total_entries: int
    analysis_cache_size: int
    synthesis_cache_size: int
    oldest_entry_age_days: float
    cache_hit_rate: float
    disk_usage_mb: float


class SystemStatusResponse(BaseModel):
    """Response model for system status."""

    status: str = "operational"
    uptime_seconds: float
    last_update: str
    database_size_mb: float
    cache: CacheStatsResponse
    api_quota_remaining: int
    api_quota_total: int = 5
    api_quota_reset_in_seconds: int


class SearchArticlesRequest(BaseModel):
    """Request model for article search."""

    search: Optional[str] = None
    source: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 20
    offset: int = 0


class FilterStats(BaseModel):
    """Statistics about filtering and deduplication."""

    total_articles_in_db: int = Field(description="Total articles in database")
    articles_after_filter: int = Field(description="Articles after relevance filtering")
    filtered_out: int = Field(description="Articles removed by relevance filter")
    articles_after_dedup: int = Field(description="Articles after deduplication")
    duplicates_grouped: int = Field(description="Duplicate articles grouped")
    trending_tags: Dict[str, Dict[str, Any]] = Field(description="Top trending security tags with counts")


class AlertsListResponse(BaseModel):
    """Response model for alerts list."""

    alerts: List[AlertResponse]
    total_count: int
    limit: int
    offset: int
    filter_stats: Optional[FilterStats] = None


class ArticlesListResponse(BaseModel):
    """Response model for articles list."""

    articles: List[ArticleResponse]
    total_count: int
    limit: int
    offset: int


class ReportsListResponse(BaseModel):
    """Response model for reports list."""

    reports: List[ReportResponse]
    total_count: int


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ExportResponse(BaseModel):
    """Response model for exported data."""

    content: str
    filename: str
    format: str  # markdown, csv, pdf


class SeverityUpdate(BaseModel):
    """Request to manually update alert severity."""

    severity: str  # critical, high, medium, low


class BookmarkToggle(BaseModel):
    """Request to toggle bookmark."""

    alert_id: int


class TagSuggestionResponse(BaseModel):
    """Response model for a suggested tag."""

    id: int
    tag: str
    category: Optional[str] = None
    first_seen: str
    last_seen: str
    article_count: int
    sample_articles: List[str] = Field(default_factory=list)
    article_ids: List[int] = Field(default_factory=list, description="Article IDs that suggested this tag")
    status: str = "pending"


class TagSuggestionsListResponse(BaseModel):
    """Response model for list of suggested tags."""

    suggestions: List[TagSuggestionResponse]
    total_count: int


class TagApprovalRequest(BaseModel):
    """Request to approve a suggested tag."""

    category: Optional[str] = Field(None, description="Category to assign the tag to (e.g., 'Threat_Actors')")
