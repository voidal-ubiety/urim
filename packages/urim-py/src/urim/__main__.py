"""``python -m urim`` runs the ``urim`` command."""

import sys

from .cli import main

sys.exit(main())
