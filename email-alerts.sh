#!/bin/bash

LOG_FILE="pytest_result.log"
RECIPIENT="admin@example.com"
SUBJECT="测试失败警报: $(hostname)"

# 运行 pytest 并将标准输出和错误输出都记录到文件
# tee 命令可以让错误同时显示在屏幕上并保存到文件
pytest tests/ 2>&1 | tee $LOG_FILE

# 获取 pytest 的退出状态码
# pytest 退出码说明: 0-成功, 1-有测试用例失败, 2-用户中断, 3-内部错误, 等
PYTEST_EXIT_CODE=${PIPESTATUS[0]}

if [ $PYTEST_EXIT_CODE -ne 0 ]; then
    echo "检测到测试失败 (Exit Code: $PYTEST_EXIT_CODE)，正在发送邮件..."
    
    # 使用 mailx 发送邮件，将日志文件作为正文
    # 如果日志太长，建议使用 -a 发送附件，正文只写摘要
    mailx -s "$SUBJECT" "$RECIPIENT" < $LOG_FILE
    
    # 确保脚本最后也以非零码退出，以便让上层调用者知道失败了
    exit $PYTEST_EXIT_CODE
else
    echo "测试全部通过！"
fi