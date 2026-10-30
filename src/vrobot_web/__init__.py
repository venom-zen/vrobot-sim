"""Live visualization web layer for the VirtualRobot kernel.

The package depends on ``vrobot_sim``; the kernel never imports it. FastAPI and uvicorn
arrive through the optional ``web`` extra, so a kernel-only install is unaffected.
"""

from vrobot_web.app import create_app

__all__ = ["create_app"]
