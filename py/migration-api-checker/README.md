# Migration API Checker

数据库迁移后 API 一致性检查工具。确保迁移前后的 API 返回完全相同的响应。

## Features

- 使用 pytest 进行测试
- 支持 YAML 配置文件定义 API
- 支持忽略指定字段（如时间戳、requestId 等）
- 支持环境变量替换
- 彩色终端输出和详细日志报告
- 可选重试机制
- 支持多线程并行测试 (`pytest-xdist`)

## Quick Start

### Try the Demo

```bash
# Terminal 1 - Start mock servers
cd py/migration-api-checker
uv run python demo_server.py both

# Terminal 2 - Run tests
cd py/migration-api-checker
uv run pytest tests/test_migration.py -v --config=cfgs.demo.yaml
```

### 1. Install dependencies

```bash
cd py/migration-api-checker
uv sync
```

### 2. Configure your APIs

Copy `cfgs.yaml` and edit it:

```bash
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
    before: "https://old-api.example.com/path"
    after: "https://new-api.example.com/path"
    headers:       # Request headers (optional)
      Authorization: "Bearer ${API_TOKEN}"  # Env var supported
    params:        # Query parameters (optional)
      key: value
    body:          # JSON request body (optional, for POST/PUT)
      field: value
    ignore_fields: # Fields to ignore in comparison
      - "timestamp"
      - "data[*].updatedAt"  # JSONPath-like pattern
```

### Ignore Fields Syntax

- Simple field: `"timestamp"`
- Nested field: `"data.createdAt"`
- Array wildcard: `"data[*].id"`
- Specific index: `"items[0].name"`

## Output

- Terminal: Colored test results and diffs
- `logs/`: Detailed logs and JSON reports

## License

MIT
