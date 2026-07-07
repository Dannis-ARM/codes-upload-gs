# 0001: Use DeepDiff for Response Comparison

Date: 2026-07-07

## Status

Accepted

## Context

The migration-api-checker initially used a hand-written JSON comparison implementation with custom JSONPath-like ignore patterns. This worked for basic cases but had several limitations:

- Maintenance overhead for the custom JSONPath parser
- Limited ignore pattern capabilities
- Suboptimal diff output readability
- No built-in support for numeric type tolerance (int vs float)

The user considered using Schemathesis + OpenAPI, but decided against it because business API endpoints require specific parameter values that aren't suitable for auto-generated fuzz testing.

## Decision

Replace the custom comparison logic with **DeepDiff**, a mature library for comparing Python data structures.

### Key Changes:

1. **Dependency**: Add `deepdiff>=6.0.0` to project dependencies
2. **Configuration**: Replace `ignore_fields` with a `compare` section that exposes DeepDiff options natively
3. **Implementation**: Rewrite `comparator.py` to use DeepDiff internally
4. **Breaking Change**: Existing `ignore_fields` syntax is no longer supported; users must migrate to DeepDiff's `exclude_paths` syntax

### DeepDiff Configuration Exposed:

- `exclude_paths`: Direct DeepDiff path exclusion (e.g., `"root['timestamp']"`, `"root['data'][*]['updatedAt']"`)
- `exclude_regex_paths`: Regex-based path exclusion
- `ignore_order`: Whether to ignore list ordering (default: `false`)
- `ignore_numeric_type_changes`: Whether to treat `1` and `1.0` as equal (default: `true` for migration scenarios)

## Rationale

### Why DeepDiff?

- **Mature & Battle-tested**: Widely adopted, actively maintained
- **Powerful Ignore Mechanisms**: `exclude_paths`, `exclude_regex_paths`, and more out of the box
- **Readable Diffs**: Built-in `pretty()` output that clearly shows what changed
- **Numeric Type Tolerance**: `ignore_numeric_type_changes` solves a common migration pain point
- **Reduced Maintenance**: No need to own the JSONPath parsing & diff generation logic

### Why NOT Schemathesis?

- Business APIs require specific, meaningful parameter values
- Auto-generated fuzz requests are often not useful for migration verification
- Existing YAML configuration approach is working well for the user's use case

## Consequences

### Positive

- Less code to maintain
- More powerful ignore capabilities
- Better diff output
- Built-in numeric type tolerance
- Access to other DeepDiff features in the future if needed

### Negative

- **Breaking Change**: Existing configurations with `ignore_fields` must be migrated
- New dependency added
- Users need to learn DeepDiff's path syntax

## Migration Guide

### Old Syntax:
```yaml
ignore_fields:
  - "timestamp"
  - "data[*].updatedAt"
```

### New Syntax:
```yaml
compare:
  exclude_paths:
    - "root['timestamp']"
    - "root['data'][*]['updatedAt']"
```

DeepDiff path syntax reference: https://zepworks.com/deepdiff/current/diff.html#exclude-paths
