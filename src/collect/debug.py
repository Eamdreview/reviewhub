"""Debug a single collector: `python -m src.collect.debug <source>`.

Runs one collector in isolation and prints what it returned, so scraper
selectors can be tuned against live HTML without running the whole pipeline.
Available sources: muncheye, producthunt, warriorplus, jvzoo, digistore24.
"""

from __future__ import annotations

import sys

from . import _REGISTRY


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in _REGISTRY:
        print(f"usage: python -m src.collect.debug <{'|'.join(_REGISTRY)}>")
        raise SystemExit(1)

    name = sys.argv[1]
    print(f"Running collector: {name}\n" + "=" * 40)
    try:
        results = _REGISTRY[name]()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}")
        raise SystemExit(2)

    print(f"Returned {len(results)} candidate(s):\n")
    for c in results[:25]:
        timing = (f"launch={c.launch_status}"
                  + (f" in {c.days_to_launch}d" if c.days_to_launch is not None else "")
                  + (f", {c.hours_since_release}h ago" if c.hours_since_release is not None else ""))
        print(f"- {c.name}  [{c.base_commission or 'no commission'}] {timing}")
        print(f"    {c.url}")


if __name__ == "__main__":
    main()
