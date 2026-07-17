# SFTP Uploader - Directory Sync Tool

Use the `sftp` command to recursively download remote directories to local. Supports merging from multiple remote sources.

## Features

- **Full recursive download**: Downloads all files every time (no incremental sync)
- **Non-destructive**: Won't delete local files, suitable for multi-source merge
- **Private key authentication**: SSH private key support
- **Dry run mode**: List remote files without downloading
- **Auto-create local directory**: Creates target directory if it doesn't exist

## Prerequisites

- Linux/macOS/WSL2 (requires `sftp` command)
- Python 3.7+

## Quick Start

### Sync from single remote source

```bash
cd py/sftp-uploader

python sync.py \
  --host example.com \
  --user myuser \
  --private-key ~/.ssh/id_rsa \
  --remote-path /remote/data \
  --local-path /local/data
```

### Sync from two remote sources to same local directory

```bash
# Source 1
python sync.py -H host1.example.com -u user1 -i ~/.ssh/id_rsa -r /data1 -l /local/merged

# Source 2 (won't delete files from source 1)
python sync.py -H host2.example.com -u user2 -i ~/.ssh/id_rsa -r /data2 -l /local/merged
```

### Dry run (list only, no download)

```bash
python sync.py \
  -H example.com \
  -u myuser \
  -i ~/.ssh/id_rsa \
  -r /remote/data \
  -l /local/data \
  --dry-run
```

### Custom port

```bash
python sync.py \
  -H example.com \
  -u myuser \
  -i ~/.ssh/id_rsa \
  -r /remote/data \
  -l /local/data \
  -P 2222
```

## All Options

| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--host` | `-H` | ✅ | - | SFTP server hostname or IP |
| `--user` | `-u` | ✅ | - | Username |
| `--private-key` | `-i` | ✅ | - | Path to private key file |
| `--remote-path` | `-r` | ✅ | - | Remote directory path |
| `--local-path` | `-l` | ✅ | - | Local directory path |
| `--port` | `-P` | ❌ | `22` | SFTP port |
| `--dry-run` | `-n` | ❌ | `false` | Dry run (list only, no download) |

## How It Works

Under the hood, this script runs:

```bash
sftp -i /path/to/key -P 22 user@host <<EOF
cd /remote/path
lcd /local/path
get -r .
quit
EOF
```

## Cron 定期运行示例

Hourly sync:

```bash
# crontab -e
0 * * * * cd /path/to/codes-upload-gs/py/sftp-uploader && python sync.py -H host1 -u user -i /key -r /remote -l /local >> /var/log/sftp-sync.log 2>&1
```
