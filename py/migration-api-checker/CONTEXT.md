# Migration API Checker - 项目术语表

## 核心概念

### API Case
单个 API 测试用例，包含：
- `name`: 测试名称
- `method`: HTTP 方法（GET/POST/PUT 等）
- `before`: 迁移前的 API URL
- `after`: 迁移后的 API URL
- `headers`: 请求头
- `params`: Query 参数
- `body`: JSON 请求体
- `compare`: DeepDiff 对比选项

### Compare Options
响应对比配置，使用 DeepDiff 原生选项：
- `exclude_paths`: 要忽略的具体路径列表
- `exclude_regex_paths`: 要忽略的路径正则列表
- `ignore_order`: 是否忽略数组顺序
- `ignore_numeric_type_changes`: 是否忽略数字类型差异（如 1 vs 1.0）

### Test Result
单个测试用例的执行结果，包含：
- `success`: 是否通过
- `before_status` / `after_status`: HTTP 状态码
- `before_elapsed` / `after_elapsed`: 请求耗时（秒）
- `diff`: 响应差异详情
- `error`: 错误信息

### Reporter
测试报告生成器，负责：
- 终端输出（Rich 彩色表格）
- JSON 报告保存
- HTML 报告生成
- 报告归档管理
