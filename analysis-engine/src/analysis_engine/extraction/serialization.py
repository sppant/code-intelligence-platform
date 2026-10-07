"""JSON (de)serialization for Import/CallSite, used to cache a file's raw
extraction results (not just resolved edges) for incremental analysis --
see pipeline.py's `previous_files` parameter. Lives here, not in backend,
because analysis-engine owns these dataclasses' shapes; backend only ever
calls these four functions, never hand-builds the dict shape itself.

Both Import and CallSite are flat frozen dataclasses with only primitive
(str/int/bool/None) fields, so a plain asdict()/keyword round-trip is exact
-- no nested-dataclass handling needed.
"""

from dataclasses import asdict

from analysis_engine.extraction.models import CallSite, Import


def import_to_dict(imp: Import) -> dict:
    return asdict(imp)


def import_from_dict(data: dict) -> Import:
    return Import(**data)


def call_site_to_dict(call: CallSite) -> dict:
    return asdict(call)


def call_site_from_dict(data: dict) -> CallSite:
    return CallSite(**data)
