#!/bin/bash

LOCKFILE="/tmp/my_process.lock"
TIMEOUT=30

# 使用 flock 尝试获取锁
# -x: 排他锁 (Exclusive lock)
# -w: 等待时间（秒）
# 200: 指定一个文件描述符
exec 200>$LOCKFILE

echo "正在尝试获取锁，最多等待 ${TIMEOUT} 秒..."

if flock -x -w $TIMEOUT 200; then
    echo "成功获取锁！开始执行任务..."
    
    # --- 这里放置你的业务逻辑 ---
    sleep 5 
    echo "任务执行完毕。"
    # -----------------------

else
    echo "错误：在 ${TIMEOUT} 秒内未能获取锁，进程退出。" >&2
    exit 1
fi