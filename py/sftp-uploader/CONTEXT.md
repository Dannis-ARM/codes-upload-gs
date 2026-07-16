# SFTP Uploader - Project Glossary

## Core Concepts

### Sync Source
A single SFTP sync source, containing:
- `host`: Server hostname/IP
- `user`: Username
- `private_key`: Path to private key file
- `remote_path`: Remote directory path
- `port`: SSH port (default 22)

### Sync Target
The sync destination, i.e., the local directory path. Supports syncing from multiple Sync Sources to the same Sync Target.

### Dry Run
Trial run mode where rsync shows what it would do without actually downloading/modifying files.

### Incremental Sync
Incremental synchronization where rsync only transfers changed parts based on file size and modification time.
