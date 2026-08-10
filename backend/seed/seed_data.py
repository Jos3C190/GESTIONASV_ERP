"""Default database seed for local and review environments.

This module intentionally remains the stable public entrypoint used by Docker,
the setup scripts and CI.  The actual business dataset lives in
``seed_grupo_lorena`` so it can also be validated independently.

Run with::

    python -m seed.seed_data
"""

from __future__ import annotations

import asyncio

from seed.seed_catalog import main as seed_catalog
from seed.seed_grupo_lorena import main

if __name__ == "__main__":
    main()
    asyncio.run(seed_catalog())
