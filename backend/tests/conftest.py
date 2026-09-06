"""Test-wide configuration that prevents local observability exports."""

import os

os.environ["PHOENIX_TRACING_ENABLED"] = "false"
