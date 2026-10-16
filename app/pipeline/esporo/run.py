import logging
import argparse

from pathlib import Path
from datetime import UTC, datetime

from .bronze import injestion_esporo
from .silver import transform_file

BASE_DIR = Path("/data")
logger = logging.getLogger(__name__)

def run(path: Path):
    run_at = datetime.now(UTC)    

    bronze = injestion_esporo(path)
    logger.info("Bronze concluída: %s", bronze)
    
    silver = transform_file(bronze, run_at=run_at)
    logger.info("Silver concluída: %s", silver)

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Pipeline Medallion ESPORO")
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    try:
        run(args.path)
    except Exception:
        logger.exception("Falha na pipeline ESPORO")
        raise SystemExit(1) from None
 
if __name__ == "__main__":
    main() 