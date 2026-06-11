"""One-off: load committed content/ + data/ files into Supabase. Idempotent."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pipeline import store
from pipeline.digest import DEFAULT_CONTENT_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("throughline")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_FRONT = re.compile(r'^---\n(.*?)\n---\n?(.*)$', re.DOTALL)


def main() -> None:
    failed = 0

    digest_files = sorted((DEFAULT_CONTENT_DIR / "digests").glob("*.json"))
    for f in digest_files:
        try:
            payload = json.loads(f.read_text())
            store.upsert_digest(payload["date"], payload)
        except Exception:
            log.exception("digest %s failed", f.name)
            failed += 1
    log.info("digests: %d migrated", len(digest_files) - failed)

    synth_files = sorted((DEFAULT_CONTENT_DIR / "synthesis").glob("*.mdx"))
    for f in synth_files:
        try:
            m = _FRONT.match(f.read_text())
            fields = dict(
                (k.strip(), v.strip().strip('"'))
                for k, v in (line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
            )
            store.upsert_synthesis(
                fields["week"], fields["title"], fields["date"], m.group(2).strip()
            )
        except Exception:
            log.exception("synthesis %s failed", f.name)
            failed += 1
    log.info("syntheses: %d migrated", len(synth_files))

    for scope, path, wrap in (
        ("summaries", DATA_DIR / "summaries" / "cache.json", False),
        ("embeddings", DATA_DIR / "embeddings" / "cache.json", True),
    ):
        if not path.exists():
            log.info("%s cache absent; skipping", scope)
            continue
        try:
            raw = json.loads(path.read_text())
            entries = {k: ({"v": v} if wrap else v) for k, v in raw.items()}
            store.cache_put(scope, entries)
            log.info("%s cache: %d entries", scope, len(entries))
        except Exception:
            log.exception("%s cache failed", scope)
            failed += 1

    if failed:
        raise SystemExit(f"{failed} migration failures")
    log.info("migration complete")


if __name__ == "__main__":
    main()
