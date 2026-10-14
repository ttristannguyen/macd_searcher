"""Offline research pipeline for signal quality — the tooling behind
docs/confidence_v3_research.md, so a periodic re-run is one command:

    uv run python -m macd_searcher.research            # top up cache, print report
    uv run python -m macd_searcher.research --offline  # cache only, no API calls
    uv run python -m macd_searcher.research --scan     # also scan every indicator

Read-only against the database. The conventions it encodes (and why) are written
down in docs/research_method.md; the short version:

  * alpha is measured against the same-run, same-class MEAN — a random pick scores 0;
  * repeat fires are grouped into episodes, and intervals resample whole weeks;
  * in-sample / out-of-sample is a date split, and new ideas are tested in-sample first;
  * features use only bars closed before the fire day.

Layering mirrors the app: ``cache`` talks to the API, ``dataset`` builds frames,
``inference`` is pure statistics, ``rules`` names the cohorts, ``__main__`` reports.
"""
