# SFTP Uploader - Directory Sync Tool

使用 rsync 通过 SSH/SFTP 协议将远程目录同步到本地。支持从多个远程源同步到同一本地目录。

## Features

- **增量同步**：只下载变化或新增的文件，节省带宽和时间
- **非破坏性**：不会删除本地文件（无 --delete），适合多源合并场景
- **私钥认证**：支持 SSH 私钥认证
- **试运行模式**：先看会发生什么再实际执行
- **进度显示**：可选详细输出和进度条

## Prerequisites

- Linux/macOS/WSL2（需要 `rsync` 和 `ssh` 命令）
- Python 3.7+

## Quick Start

### 从单个远程源同步

```bash
cd py/sftp-uploader

python sync.py \
  --host example.com \
  --user myuser \
  --private-key ~/.ssh/id_rsa \
  --remote-path /remote/data \
  --local-path /local/data
```

### 从两个远程源同步到同一本地目录

```bash
# 源 1
python sync.py -H host1.example.com -u user1 -i ~/.ssh/id_rsa -r /data1 -l /local/merged

# 源 2（不会删除源 1 的文件）
python sync.py -H host2.example.com -u user2 -i ~/.ssh/id_rsa -r /data2 -l /local/merged
```

### 试运行（不实际下载）

```bash
python sync.py \
  -H example.com \
  -u myuser \
  -i ~/.ssh/id_rsa \
  -r /remote/data \
  -l /local/data \
  --dry-run
```

### 详细输出 + 进度条 + 自定义端口

```bash
python sync.py \
  -H example.com \
  -u myuser \
  -i ~/.ssh/id_rsa \
  -r /remote/data \
  -l /local/data \
  -p 2222 \
  --verbose
```

## All Options

| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--host` | `-H` | ✅ | - | SFTP 服务器主机名或 IP |
| `--user` | `-u` | ✅ | - | 用户名 |
| `--private-key` | `-i` | ✅ | - | 私钥文件路径 |
| `--remote-path` | `-r` | ✅ | - | 远程目录路径 |
| `--local-path` | `-l` | ✅ | - | 本地目录路径 |
| `--port` | `-p` | ❌ | `22` | SSH 端口 |
| `--dry-run` | `-n` | ❌ | `false` | 试运行，不实际下载 |
| `--verbose` | `-v` | ❌ | `false` | 详细输出 + 进度条 |

## How It Works

底层使用 `rsync` 命令，参数为：
```bash
rsync -avz -e "ssh -i /path/to/key -p 22" user@host:/remote/path/ /local/path/
```

- `-a`: Archive 模式（递归 + 保留权限、时间戳、符号链接等）
- `-v`: 详细输出
- `-z`: 传输时压缩数据

## Cron 定期运行示例

每小时同步一次：

```bash
# crontab -e
0 * * * * cd /path/to/codes-upload-gs/py/sftp-uploader && python sync.py -H host1 -u user -i /key -r /remote -l /local >> /var/log/sftp-sync.log 2>&1
```
