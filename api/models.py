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
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class ReportResponse(BaseModel):
    """Response model for synthesis reports."""

    id: Optional[int] = None
    report_content: str
    articles_count: int
    generated_date: str
    timestamp: datetime = Field(default_factory=datetime.now)


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


class AlertsListResponse(BaseModel):
    """Response model for alerts list."""

    alerts: List[AlertResponse]
    total_count: int
    limit: int
    offset: int


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
