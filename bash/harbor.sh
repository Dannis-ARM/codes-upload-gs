# 执行创建并获取 HTTP 状态码
response=$(curl -u "admin:Harbor12345" -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  "https://harbor.example.com/api/v2.0/projects" \
  -d '{"project_name": "new-project", "metadata": { "public": "false" }}')

if [ "$response" == "409" ]; then
  echo "项目已存在，无需处理。"
elif [ "$response" == "201" ]; then
  echo "项目创建成功。"
else
  echo "发生意外错误，状态码: $response"
fi