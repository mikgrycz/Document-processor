"""Errors raised while fetching or processing a document.

The worker uses the type (not the message) to decide whether to retry.
"""

from __future__ import annotations


class ProcessingError(Exception):
    """Base class for fetch/processing failures."""


class TransientProcessingError(ProcessingError):
    """A retryable failure: timeout, connection error, 5xx response, etc."""


class PermanentProcessingError(ProcessingError):
    """A non-retryable failure: 4xx response, oversized body, bad URL, etc."""
