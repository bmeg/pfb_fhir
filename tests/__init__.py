"""Test package."""

import os
import glob
import logging
from pfb_fhir.emitter import STATIC_ENTITIES

logger = logging.getLogger(__name__)


def _keep_me(path):
    """Don't delete these files."""
    for file in STATIC_ENTITIES:
        if file in path:
            return True
    return False


def cleanup_emitter(output_path, pfb_path):
    """Delete files."""
    for path in glob.glob(f"{output_path}/gen3/*.yaml"):
        if _keep_me(path):
            continue
        os.remove(path)
        logger.debug(f"Removed {path}")
    for path in glob.glob(f"{output_path}/pfb/*.ndjson"):
        os.remove(path)
        logger.debug(f"Removed {path}")

    os.remove(pfb_path)
    logger.debug(f"Removed {pfb_path}")

    dump_path = f"{output_path}/dump-ordered.json"
    if os.path.isfile(dump_path):
        os.remove(dump_path)
        logger.debug(f"Removed {dump_path}")
