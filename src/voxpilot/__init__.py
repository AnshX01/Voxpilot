"""VoxPilot core package."""

import sys
from voxpilot import contracts

__version__ = "0.1.0"

# Register PascalCase and hybrid aliases in sys.modules for backwards compatibility
sys.modules.setdefault("VoxPilot", sys.modules[__name__])
sys.modules.setdefault("VoxPilot.Contracts", contracts)
sys.modules.setdefault("VoxPilot.contracts", contracts)
