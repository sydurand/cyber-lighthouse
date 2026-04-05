"""Report-related API routes."""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
import io
from datetime import datetime

from cache import get_cache
from export_utils import generate_report_toc, export_report_to_markdown
from logging_config import logger
from .models import (
    ReportsListResponse,
    ReportResponse,
    ReportWithTOC,
    ReportTOCItem,
)

router = APIRouter(prefix="/api", tags=["reports"])

cache = get_cache()


@router.get("/reports", response_model=ReportsListResponse)
async def get_reports(
    limit: int = Query(10, ge=1, le=50),
) -> ReportsListResponse:
    """Get daily synthesis reports."""
    try:
        reports = []
        synthesis_reports = cache.get_synthesis_reports()

        for report in synthesis_reports[:limit]:
            articles_count = report.get("articles_count", 0)
            if articles_count == 0 and report.get("content"):
                import re
                list_items = re.findall(r'^[\s]*[-*]\s+', report["content"], re.MULTILINE)
                articles_count = max(1, len(list_items) // 2)

            reports.append(ReportResponse(
                report_content=report.get("content", "Report not available"),
                articles_count=articles_count,
                generated_date=report.get("generated_date", datetime.now().strftime("%Y-%m-%d")),
                report_id=report.get("cache_key", ""),
            ))

        return ReportsListResponse(reports=reports, total_count=len(reports))

    except Exception as e:
        logger.error(f"Error fetching reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/reports/{report_index}/toc")
async def get_report_toc_endpoint(report_index: int) -> ReportWithTOC:
    """Get report with table of contents."""
    try:
        report = cache.get_synthesis_report_by_index(report_index)
        if not report:
            return ReportWithTOC(
                report=ReportResponse(report_content="", articles_count=0, generated_date=""),
                table_of_contents=[]
            )

        content = report.get("content", "")
        toc_items = generate_report_toc(content)

        articles_count = report.get("articles_count", 0)
        if articles_count == 0 and content:
            import re
            list_items = re.findall(r'^[\s]*[-*]\s+', content, re.MULTILINE)
            articles_count = max(1, len(list_items) // 2)

        report_response = ReportResponse(
            report_content=content,
            articles_count=articles_count,
            generated_date=report.get("generated_date", ""),
            report_id=report.get("cache_key", ""),
        )

        toc_items_formatted = [
            ReportTOCItem(level=item["level"], text=item["text"], anchor=item["anchor"])
            for item in toc_items
        ]

        return ReportWithTOC(report=report_response, table_of_contents=toc_items_formatted)

    except Exception as e:
        logger.error(f"Error generating report TOC: {e}")
        return ReportWithTOC(
            report=ReportResponse(report_content="", articles_count=0, generated_date=""),
            table_of_contents=[]
        )


@router.get("/export/report/{report_index}")
async def export_report(report_index: int, format: str = Query("markdown", pattern="^(markdown)$")):
    """Export a specific report as a downloadable file."""
    try:
        report = cache.get_synthesis_report_by_index(report_index)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        content = report.get("content", "")
        date = report.get("generated_date", "unknown")

        if format == "markdown":
            export_content = export_report_to_markdown(content, date)
            filename = f"report_{date}.md"
            media_type = "text/markdown"
        else:
            export_content = content
            filename = f"report_{date}.txt"
            media_type = "text/plain"

        return StreamingResponse(
            io.BytesIO(export_content.encode("utf-8")),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
