"""
Error handling utilities for consistent error responses and logging.
"""

from functools import wraps
from typing import Callable, Any, Optional
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from logger_config import logger


class AphoriumError(Exception):
    """Base exception for Aphorium application errors."""
    
    def __init__(self, message: str, code: str = "GENERAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class QuoteNotFoundError(AphoriumError):
    """Raised when a quote is not found."""
    
    def __init__(self, quote_id: Optional[int] = None):
        message = f"Quote not found" + (f" (ID: {quote_id})" if quote_id else "")
        super().__init__(message, code="QUOTE_NOT_FOUND", status_code=404)


class DatabaseError(AphoriumError):
    """Raised when a database operation fails."""
    
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, code="DATABASE_ERROR", status_code=500)


def format_error_response(error: Exception) -> dict:
    """
    Format error as standard API response.
    
    Args:
        error: Exception to format
        
    Returns:
        Formatted error dictionary
    """
    if isinstance(error, AphoriumError):
        return {
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {}
            }
        }
    elif isinstance(error, HTTPException):
        return {
            "error": {
                "code": "HTTP_ERROR",
                "message": error.detail,
                "details": {"status_code": error.status_code}
            }
        }
    else:
        return {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {}
            }
        }


def handle_db_errors(func: Callable) -> Callable:
    """
    Decorator for database error handling.
    
    Automatically handles IntegrityError and SQLAlchemyError,
    converting them to appropriate exceptions.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f"Database integrity error in {func.__name__}: {e}")
            raise DatabaseError(f"Database integrity error: {str(e)}")
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise DatabaseError(f"Database error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            raise
    
    return wrapper


def log_errors(func: Callable) -> Callable:
    """
    Decorator for logging errors.
    
    Logs errors without modifying them.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise
    
    return wrapper

