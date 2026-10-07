from analysis_engine.graph.cycles import find_cycles
from analysis_engine.graph.impact import affected_files, compute_risk_indicators, is_test_file
from analysis_engine.graph.insights import compute_architecture_insights
from analysis_engine.graph.metrics import fan_in_out, isolated_files, large_files


# --- cycles ---


def test_find_cycles_detects_a_true_cycle():
    nodes = ["a.py", "b.py", "c.py"]
    edges = [("a.py", "b.py"), ("b.py", "c.py"), ("c.py", "a.py")]
    cycles = find_cycles(nodes, edges)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a.py", "b.py", "c.py"}


def test_find_cycles_ignores_a_simple_chain():
    nodes = ["a.py", "b.py", "c.py"]
    edges = [("a.py", "b.py"), ("b.py", "c.py")]
    assert find_cycles(nodes, edges) == []


def test_find_cycles_handles_disconnected_components():
    nodes = ["a.py", "b.py", "c.py", "d.py"]
    edges = [("a.py", "b.py"), ("b.py", "a.py"), ("c.py", "d.py")]
    cycles = find_cycles(nodes, edges)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a.py", "b.py"}


def test_find_cycles_detects_self_loop():
    nodes = ["a.py"]
    edges = [("a.py", "a.py")]
    cycles = find_cycles(nodes, edges)
    assert cycles == [["a.py"]]


def test_find_cycles_handles_many_nodes_without_recursion_error():
    # A long chain is exactly the shape that would blow Python's recursion
    # limit with a naive recursive Tarjan implementation.
    n = 5000
    nodes = [f"f{i}.py" for i in range(n)]
    edges = [(f"f{i}.py", f"f{i + 1}.py") for i in range(n - 1)]
    assert find_cycles(nodes, edges) == []


# --- metrics ---


def test_fan_in_out_counts():
    nodes = ["a.py", "b.py", "c.py"]
    edges = [("a.py", "b.py"), ("c.py", "b.py")]
    counts = fan_in_out(nodes, edges)
    assert counts["b.py"] == (2, 0)
    assert counts["a.py"] == (0, 1)
    assert counts["c.py"] == (0, 1)


def test_large_files_sorted_largest_first():
    files = [("small.py", 10), ("big.py", 1000), ("medium.py", 500)]
    assert large_files(files, threshold=400) == ["big.py", "medium.py"]


def test_isolated_files_excludes_connected_nodes():
    nodes = ["a.py", "b.py", "lonely.py"]
    edges = [("a.py", "b.py")]
    assert isolated_files(nodes, edges) == ["lonely.py"]


# --- impact ---


def test_is_test_file_by_directory():
    assert is_test_file("tests/test_foo.py")
    assert is_test_file("src/__tests__/foo.test.ts")
    assert not is_test_file("src/foo.py")


def test_is_test_file_by_filename_pattern():
    assert is_test_file("foo/test_bar.py")
    assert is_test_file("foo/bar_test.py")
    assert is_test_file("foo/bar.test.ts")
    assert is_test_file("foo/bar.spec.tsx")
    assert not is_test_file("foo/bar.py")


def test_affected_files_transitive_reverse_dependents():
    # a.py -> b.py -> c.py: changing c.py affects both a.py and b.py.
    edges = [("a.py", "b.py"), ("b.py", "c.py")]
    assert affected_files("c.py", edges) == {"a.py", "b.py"}


def test_affected_files_excludes_target_itself():
    edges = [("a.py", "a.py")]
    assert affected_files("a.py", edges) == set()


def test_compute_risk_indicators_thresholds():
    indicators = compute_risk_indicators(
        fan_in=15,
        affected_files_count=5,
        affected_tests_count=0,
        direct_callers_count=0,
        symbol_kind="function",
    )
    assert "High coupling" in indicators
    assert "Missing test coverage" in indicators
    assert any("No direct callers" in i for i in indicators)
    assert "Wide blast radius" not in indicators


def test_compute_risk_indicators_clean_symbol_has_no_flags():
    indicators = compute_risk_indicators(
        fan_in=1,
        affected_files_count=1,
        affected_tests_count=2,
        direct_callers_count=3,
        symbol_kind="function",
    )
    assert indicators == []


# --- insights ---


def test_compute_architecture_insights_integrates_all_algorithms():
    files = [("a.py", 10), ("b.py", 600), ("lonely.py", 5)]
    edges = [("a.py", "b.py"), ("b.py", "a.py")]  # a cycle between a and b
    insights = compute_architecture_insights(files, edges, large_file_threshold=400)

    assert set(insights.cycles[0]) == {"a.py", "b.py"}
    assert insights.large_files == ["b.py"]
    assert insights.isolated_files == ["lonely.py"]
    fan_in_out_by_path = {f.path: (f.fan_in, f.fan_out) for f in insights.fan_in_out}
    assert fan_in_out_by_path["a.py"] == (1, 1)
    assert fan_in_out_by_path["b.py"] == (1, 1)
