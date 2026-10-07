from collections.abc import Iterable


def _tarjan_scc(nodes: Iterable[str], adj: dict[str, list[str]]) -> list[list[str]]:
    """Iterative (not recursive) Tarjan's strongly-connected-components
    algorithm -- avoids Python's recursion limit on long import chains in a
    large repository. Simulates the recursive call stack explicitly with
    `work_stack`, a list of (node, neighbor-iterator) pairs.
    """
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    tarjan_stack: list[str] = []
    result: list[list[str]] = []
    next_index = 0

    for start in nodes:
        if start in index:
            continue

        work_stack: list[tuple[str, Iterable[str]]] = [(start, iter(adj.get(start, ())))]
        index[start] = lowlink[start] = next_index
        next_index += 1
        tarjan_stack.append(start)
        on_stack[start] = True

        while work_stack:
            node, neighbors = work_stack[-1]
            neighbor = next(neighbors, None)

            if neighbor is not None:
                if neighbor not in index:
                    index[neighbor] = lowlink[neighbor] = next_index
                    next_index += 1
                    tarjan_stack.append(neighbor)
                    on_stack[neighbor] = True
                    work_stack.append((neighbor, iter(adj.get(neighbor, ()))))
                elif on_stack.get(neighbor):
                    lowlink[node] = min(lowlink[node], index[neighbor])
                continue

            # Neighbor iterator exhausted for `node`.
            work_stack.pop()
            if work_stack:
                parent = work_stack[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
            if lowlink[node] == index[node]:
                component = []
                while True:
                    w = tarjan_stack.pop()
                    on_stack[w] = False
                    component.append(w)
                    if w == node:
                        break
                result.append(component)

    return result


def find_cycles(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[list[str]]:
    """Find circular dependency chains among `nodes` connected by `edges`
    (source, target) pairs -- e.g. file-level "imports" edges. Returns each
    non-trivial strongly-connected component (more than one node, or a
    single node with a genuine self-loop) as a list of paths.
    """
    node_list = list(nodes)
    adj: dict[str, list[str]] = {}
    for source, target in edges:
        adj.setdefault(source, []).append(target)

    components = _tarjan_scc(node_list, adj)

    cycles = []
    for component in components:
        if len(component) > 1:
            cycles.append(component)
        elif len(component) == 1:
            node = component[0]
            if node in adj.get(node, ()):
                cycles.append(component)
    return cycles
