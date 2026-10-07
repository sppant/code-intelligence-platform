from pathlib import Path

from analysis_engine.parsing import python_parser, ts_js_parser


def test_python_parser_accepts_valid_source():
    assert python_parser.parse_ok("def f():\n    return 1\n") is True


def test_python_parser_rejects_invalid_source():
    assert python_parser.parse_ok("def f(:\n") is False


def test_ts_js_parser_accepts_valid_javascript():
    source = b"function f() { return 1; }\n"
    assert ts_js_parser.parse_ok(source, Path("f.js")) is True


def test_ts_js_parser_accepts_valid_typescript():
    source = b"function f(): number { return 1; }\n"
    assert ts_js_parser.parse_ok(source, Path("f.ts")) is True


def test_ts_js_parser_flags_syntax_error():
    source = b"function f( { return 1; }\n"
    assert ts_js_parser.parse_ok(source, Path("f.js")) is False
