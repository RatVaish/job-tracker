from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db


# Remove the wrapper - just use get_db directly
# This was causing the issue


def validate_pagination(
        skip: int = 0,
        limit: int = 100
) -> dict:
    """
    Dependency for validating pagination parameters.
    Ensures skip >= 0 and limit is between 1 and 100.

    Usage:
        @app.get("/items")
        def read_items(
            pagination: dict = Depends(validate_pagination),
            db: Session = Depends(get_db)
        ):
            skip = pagination["skip"]
            limit = pagination["limit"]
            return db.query(Item).offset(skip).limit(limit).all()
    """
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip must be >= 0"
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100"
        )

    return {"skip": skip, "limit": limit}
