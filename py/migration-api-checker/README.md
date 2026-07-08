# Migration API Checker

数据库迁移后 API 一致性检查工具。确保迁移前后的 API 返回完全相同的响应。

## Features

- pytest 测试框架
- YAML 配置定义 API
- **DeepDiff 响应对比** + 快速预检查（数组长度、dict keys）
- 环境变量替换
- 彩色终端输出 + 详细 JSON/HTML 报告
- 重试机制
- 并行测试（`pytest-xdist`）
- 忽略 SSL 证书验证
- Query Params 可写在 URL 里或单独配置，自动合并
- 特殊字符透传（`[]`、`.` 等）
- Test Name 超长智能截断（>50字符）+ hover 显示完整名称
- Duration 毫秒级精度显示

## Quick Start

### Try the Demo

```bash
# Terminal 1 - Start mock servers
cd py/migration-api-checker
uv run python demo_server.py both

# Terminal 2 - Run tests
uv run pytest tests/test_migration.py -v --config=cfgs.demo.yaml
```

### 1. Install dependencies

```bash
cd py/migration-api-checker
uv sync
```

### 2. Configure your APIs

Copy `cfgs.demo.yaml` and edit it:

```bash
cp cfgs.demo.yaml cfgs.yaml
cp .env.example .env
# Edit .env with your API tokens
# Edit cfgs.yaml with your API endpoints
```

### 3. Run tests

```bash
uv run pytest tests/test_migration.py -v
```

Or with custom config file:

```bash
uv run pytest tests/test_migration.py -v --config=my_config.yaml
```

Run with multi-threading (faster):

```bash
# Auto-detect CPU cores
uv run pytest tests/test_migration.py -v --config=cfgs.demo.yaml -n auto

# Or specify number of workers
uv run pytest tests/test_migration.py -v --config=cfgs.demo.yaml -n 4
```

Skip HTML report for faster runs:

```bash
SKIP_HTML=1 uv run pytest tests/test_migration.py -v --config=cfgs.yaml
```

## Configuration

### cfgs.yaml format

```yaml
global:
  common_headers:  # Common headers for all APIs
    User-Agent: "Migration-Checker/1.0"
  timeout: 30      # Request timeout in seconds
  retries: 0       # Number of retries (0 = no retry)

apis:
  - name: "API Name"
    method: "GET"  # HTTP method: GET, POST, PUT, DELETE, PATCH
    before: "https://old-api.example.com/path?param1=value1"  # Query params can be in URL
    after: "https://new-api.example.com/path?param1=value1"
    headers:       # Request headers (optional)
      Authorization: "Bearer ${API_TOKEN}"  # Env var supported
    params:        # Query parameters (optional, merged with URL params, config overrides URL)
      key: value
    body:          # JSON request body (optional, for POST/PUT)
      field: value
    compare:       # DeepDiff comparison options (optional)
      exclude_paths:
        - "root['timestamp']"
        - "root['data'][*]['updatedAt']"
      exclude_regex_paths:
        - "root\\['data'\\]\\[\\d+\\]\\['createdAt'\\]"
      ignore_order: false
      ignore_numeric_type_changes: true
```

### Query Params

Query params 可以直接写在 URL 里，也可以放在 `params` 配置里：
- 如果两者同时存在，会合并，`params` 配置覆盖 URL 里的
- 特殊字符如 `[]`、`.` 等会透传，不做 URL encode

### Compare Options (DeepDiff)

使用 DeepDiff 原生配置，详细文档：https://zepworks.com/deepdiff/current/diff.html

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `exclude_paths` | `List[str]` | `[]` | 要忽略的具体路径 |
| `exclude_regex_paths` | `List[str]` | `[]` | 要忽略的路径正则表达式 |
| `ignore_order` | `bool` | `true` | 是否忽略数组顺序 |
| `ignore_numeric_type_changes` | `bool` | `true` | 是否忽略数字类型差异（`1` vs `1.0`） |

### Path Syntax Examples

DeepDiff 使用 Python repr 风格的路径：

| Description | Syntax |
|-------------|--------|
| 根级字段 | `"root['timestamp']"` |
| 嵌套字段 | `"root['data']['user']['id']"` |
| 数组通配符 | `"root['data'][*]['updatedAt']"` |
| 数组索引 | `"root['items'][0]['name']"` |
| 正则 | `r"root\['data'\]\[\d+\]\['createdAt'\]"` |

### Performance Tips for Large Responses

If you have APIs returning large arrays (1000+ items):

1. **Use `ignore_order: true`** if order doesn't matter
2. **Add `exclude_paths`** for large arrays you don't need to compare
3. **Use `SKIP_HTML=1`** for faster runs when you only need JSON/terminal output
4. **Use parallel testing** with `-n auto`

## Output

- Terminal: Colored test results and diffs
- `logs/current/`: Latest reports (JSON + HTML)
- `logs/archive/`: Timestamped archived reports

## ADRs

重要架构决策记录在 [docs/adr/](docs/adr/)：
- [0001: Use DeepDiff for Response Comparison](docs/adr/0001-use-deepdiff-for-comparison.md)

## License

MIT
