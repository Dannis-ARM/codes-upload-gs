#!/usr/bin/env python3
"""
根据进程名查找配置文件

功能：
1. 根据进程名找到进程PID和可执行文件路径
2. 在多个位置搜索配置文件：
   - 进程可执行文件同目录
   - /etc 目录
   - 进程的工作目录
   - 用户配置目录 (~/.config)
3. 支持常见配置文件类型: .conf, .config, .ini, .yaml, .yml, .json, .toml, .xml, .properties, .cfg

用法：
    python find_config_by_process.py <进程名> [--path <自定义搜索路径>]
"""

import os
import sys
import argparse
import subprocess
import glob
from pathlib import Path
from typing import List, Set

# 支持的配置文件扩展名
CONFIG_EXTENSIONS = {
    '.conf', '.config', '.cfg',
    '.ini', '.yaml', '.yml',
    '.json', '.toml', '.xml',
    '.properties', '.env'
}

# 常见的配置文件名模式
CONFIG_PATTERNS = [
    '*config*', '*.conf', '*.cfg', '*.ini',
    '*.yaml', '*.yml', '*.json', '*.toml',
    '*.xml', '*.properties', '.env*'
]


def get_process_info(process_name: str) -> List[dict]:
    """获取进程信息列表"""
    processes = []
    
    try:
        # 使用 ps 命令获取进程信息
        cmd = ['ps', 'aux']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            print(f"警告: 无法获取进程列表: {result.stderr}")
            return []
        
        for line in result.stdout.split('\n')[1:]:  # 跳过标题行
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) < 11:
                continue
            
            # 检查进程名是否匹配
            # 最后一列通常是完整的命令
            cmd_str = ' '.join(parts[10:])
            
            if process_name in os.path.basename(cmd_str) or process_name in parts[10]:
                pid = parts[1]
                # 获取可执行文件路径
                exe_path = parts[10] if os.path.isabs(parts[10]) else ''
                
                # 获取工作目录 (通过 /proc/PID/cwd)
                try:
                    cwd = os.readlink(f'/proc/{pid}/cwd')
                except:
                    cwd = ''
                
                # 获取命令行
                cmdline_path = f'/proc/{pid}/cmdline'
                if os.path.exists(cmdline_path):
                    with open(cmdline_path, 'r') as f:
                        cmdline = f.read().replace('\x00', ' ')
                else:
                    cmdline = cmd_str
                
                processes.append({
                    'pid': pid,
                    'exe': exe_path,
                    'cwd': cwd,
                    'cmdline': cmdline
                })
    
    except subprocess.TimeoutExpired:
        print("错误: 获取进程信息超时")
    except Exception as e:
        print(f"错误: 获取进程信息失败: {e}")
    
    return processes


def get_process_exe_path(process_name: str) -> str:
    """获取进程的可执行文件路径"""
    try:
        # 使用 pgrep 获取进程PID
        result = subprocess.run(
            ['pgrep', '-f', process_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip().split('\n')[0]
            
            # 读取可执行文件路径
            exe_link = f'/proc/{pid}/exe'
            if os.path.exists(exe_link):
                exe_path = os.readlink(exe_link)
                # 去除参数部分
                return exe_path.split()[0] if ' ' in exe_path else exe_path
    
    except Exception as e:
        print(f"警告: 使用 pgrep 查找进程失败: {e}")
    
    # 备用方法：使用 ps 命令
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        for line in result.stdout.split('\n')[1:]:
            if process_name in line:
                parts = line.split()
                if len(parts) >= 11:
                    exe = parts[10]
                    if os.path.isabs(exe):
                        return exe
    except:
        pass
    
    return ''


def search_configs_in_directory(directory: str, extensions: Set[str], depth: int = 3) -> List[str]:
    """在指定目录中搜索配置文件"""
    found_configs = []
    
    if not os.path.isdir(directory):
        return found_configs
    
    try:
        for root, dirs, files in os.walk(directory):
            # 限制搜索深度
            depth_check = root[len(directory):].count(os.sep)
            if depth_check >= depth:
                dirs.clear()
                continue
            
            # 跳过某些系统目录
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', '.cache']]
            
            for filename in files:
                # 检查扩展名
                _, ext = os.path.splitext(filename)
                if ext.lower() in extensions:
                    full_path = os.path.join(root, filename)
                    found_configs.append(full_path)
                
                # 检查常见的配置文件名模式
                filename_lower = filename.lower()
                if any(pattern.replace('*', '') in filename_lower for pattern in ['config', 'conf', 'cfg', 'ini', 'settings']):
                    if ext.lower() not in extensions:
                        full_path = os.path.join(root, filename)
                        found_configs.append(full_path)
    
    except PermissionError:
        pass
    except Exception as e:
        print(f"警告: 搜索目录 {directory} 时出错: {e}")
    
    return found_configs


def find_configs_for_process(process_name: str, custom_path: str = None) -> dict:
    """查找进程相关的配置文件"""
    results = {
        'process_info': None,
        'config_locations': {}
    }
    
    # 获取进程信息
    processes = get_process_info(process_name)
    
    if not processes:
        print(f"未找到进程: {process_name}")
        return results
    
    results['process_info'] = processes[0]
    
    # 收集所有搜索路径
    search_paths = set()
    
    # 1. 进程可执行文件目录
    for proc in processes:
        if proc.get('exe'):
            exe_dir = os.path.dirname(proc['exe'])
            if exe_dir and os.path.isdir(exe_dir):
                search_paths.add(exe_dir)
        
        # 2. 进程工作目录
        if proc.get('cwd') and os.path.isdir(proc['cwd']):
            search_paths.add(proc['cwd'])
    
    # 3. 常用配置目录
    user_config_base = os.path.expanduser('~/.config')
    user_home = os.path.expanduser('~')
    
    common_config_dirs = [
        '/etc',
        f'/etc/{process_name}',
        '/etc/init.d',
        '/etc/sysconfig',
        '/etc/systemd/system',
        user_config_base,
        f'{user_config_base}/{process_name}',
        f'{user_home}/.{process_name}',
    ]
    
    for d in common_config_dirs:
        if os.path.isdir(d):
            search_paths.add(d)
    
    # 4. 自定义路径
    if custom_path and os.path.isdir(custom_path):
        search_paths.add(custom_path)
    
    # 搜索配置文件
    for path in sorted(search_paths):
        configs = search_configs_in_directory(path, CONFIG_EXTENSIONS)
        if configs:
            results['config_locations'][path] = configs
    
    return results


def print_results(results: dict, process_name: str):
    """打印搜索结果"""
    print(f"\n{'='*60}")
    print(f"进程 '{process_name}' 的配置文件搜索结果")
    print(f"{'='*60}\n")
    
    if not results.get('process_info'):
        print("未找到相关进程信息")
        return
    
    proc = results['process_info']
    print(f"PID: {proc.get('pid', 'N/A')}")
    print(f"可执行文件: {proc.get('exe', 'N/A')}")
    print(f"工作目录: {proc.get('cwd', 'N/A')}")
    print(f"命令行: {proc.get('cmdline', 'N/A')[:100]}...")
    
    print(f"\n{'='*60}")
    print("找到的配置文件:")
    print(f"{'='*60}\n")
    
    if not results.get('config_locations'):
        print("未找到配置文件")
        return
    
    for location, configs in results['config_locations'].items():
        print(f"\n📁 目录: {location}")
        print("-" * 50)
        for config in sorted(configs):
            size = os.path.getsize(config) if os.path.exists(config) else 0
            print(f"  📄 {config} ({size} bytes)")


def main():
    parser = argparse.ArgumentParser(
        description='根据进程名查找配置文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python find_config_by_process.py nginx
  python find_config_by_process.py python
  python find_config_by_process.py myapp --path /opt/myapp
  python find_config_by_process.py java --path /home/user/configs
        """
    )
    
    parser.add_argument(
        'process_name',
        help='进程名 (可以是完整名或部分名)'
    )
    
    parser.add_argument(
        '--path', '-p',
        help='额外的搜索路径'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细信息'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        print(f"搜索进程: {args.process_name}")
        if args.path:
            print(f"额外搜索路径: {args.path}")
    
    results = find_configs_for_process(args.process_name, args.path)
    print_results(results, args.process_name)


if __name__ == '__main__':
    main()
