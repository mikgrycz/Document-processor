"""Prometheus metrics for the service.

job_duration_seconds measures a single processing attempt (fetch +
process), not the full multi-retry lifetime of a job.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

jobs_submitted_total = Counter("jobs_submitted_total", "Jobs submitted", ["operation"])
jobs_completed_total = Counter(
    "jobs_completed_total", "Jobs that reached a terminal state", ["status"]
)
job_retries_total = Counter("job_retries_total", "Jobs re-queued after a transient failure")
jobs_queue_depth = Gauge("jobs_queue_depth", "Jobs currently waiting to be processed")
job_duration_seconds = Histogram("job_duration_seconds", "Duration of a single processing attempt")
