from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DetectColumnName(BaseModel):
    top_rows: str

class ExcelColumnDetectionResult(BaseModel):
    """Result section: relevant columns and irrelevant data."""
    columns: Dict[str, int] = Field(
        ..., description="Mapping of recognized column keys to their column indexes."
    )
    irrelevant_columns: List[int] = Field(
        default_factory=list,
        description="List of column indexes not matching any known column names."
    )
    irrelevant_rows: List[int] = Field(
        default_factory=list,
        description="List of row indexes that should be removed (empty, totals, or irrelevant)."
    )

class UsageStats(BaseModel):
    """Usage statistics for AI file processing."""
    ai_processing: int = Field(..., description="Number of AI files processed")
    ai_files_remaining: int = Field(..., description="Number of AI files remaining")
    ai_files_limit: int = Field(..., description="Total AI files limit for the plan")
    daily_regeneration: int = Field(..., description="Number of files that regenerate daily")
    last_regenerated_at: Optional[datetime] = Field(None, description="Last time credits were regenerated")

class ExcelColumnDetectionResponse(BaseModel):
    """Successful model response."""
    ok: bool = Field(True, description="Whether the detection succeeded.")
    result: ExcelColumnDetectionResult = Field(
        ..., description="Parsed JSON result with detected columns and irrelevant data."
    )
