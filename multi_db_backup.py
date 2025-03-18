#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import configparser
import argparse
import logging
import subprocess
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("multi_db_backup.log")
    ]
)
logger = logging.getLogger("multi_db_backup")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='从配置文件备份多个数据库到WebDAV网盘')
    parser.add_argument('--config', default='db_config.ini', help='配置文件路径，默认为db_config.ini')
    parser.add_argument('--parallel', type=int, default=2, help='并行备份的数据库数量，默认为2')
    parser.add_argument('--database', help='只备份指定数据库，不指定则备份所有数据库')
    return parser.parse_args()

def read_config(config_file):
    """读取配置文件"""
    if not os.path.exists(config_file):
        logger.error(f"配置文件不存在: {config_file}")
        sys.exit(1)
        
    logger.info(f"读取配置文件: {config_file}")
    config = configparser.ConfigParser()
    config.read(config_file)
    
    return config

def backup_database(db_config, global_config):
    """备份单个数据库"""
    db_name = db_config.get('name')
    db_type = db_config.get('type')
    logger.info(f"开始备份数据库: {db_name} (类型: {db_type})")
    
    # 构建备份命令
    cmd = [
        sys.executable, 
        "db_backup.py",
        f"--db-type={db_type}",
        f"--db-name={db_name}",
        f"--webdav-url={global_config['webdav_url']}",
        f"--webdav-username={global_config['webdav_username']}",
        f"--webdav-password={global_config['webdav_password']}",
    ]
    
    # 添加数据库特定参数
    if 'user' in db_config:
        cmd.append(f"--db-user={db_config['user']}")
        
    if 'password' in db_config:
        cmd.append(f"--db-password={db_config['password']}")
        
    if 'host' in db_config:
        cmd.append(f"--db-host={db_config['host']}")
        
    if 'port' in db_config:
        cmd.append(f"--db-port={db_config['port']}")
        
    if 'file' in db_config:
        cmd.append(f"--db-file={db_config['file']}")
        
    if 'custom_cmd' in db_config:
        cmd.append(f"--custom-cmd={db_config['custom_cmd']}")
    
    # 确定WebDAV路径
    if 'backup_path' in db_config:
        webdav_path = db_config['backup_path']
    else:
        webdav_path = os.path.join(global_config['base_backup_path'], db_type)
        
    cmd.append(f"--webdav-path={webdav_path}")
    
    # 设置最大备份数量
    if 'max_backups' in db_config:
        max_backups = db_config['max_backups']
    else:
        max_backups = global_config['max_backups']
        
    cmd.append(f"--max-backups={max_backups}")
    
    # 执行备份命令
    try:
        logger.info(f"执行备份命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            logger.info(f"数据库 {db_name} 备份成功")
            return True, db_name, None
        else:
            logger.error(f"数据库 {db_name} 备份失败: {result.stderr}")
            return False, db_name, result.stderr
            
    except Exception as e:
        logger.error(f"备份数据库 {db_name} 时发生错误: {str(e)}")
        return False, db_name, str(e)

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 读取配置文件
    config = read_config(args.config)
    
    # 获取全局配置
    global_config = {
        'webdav_url': config.get('global', 'webdav_url'),
        'webdav_username': config.get('global', 'webdav_username'),
        'webdav_password': config.get('global', 'webdav_password'),
        'base_backup_path': config.get('global', 'base_backup_path'),
        'max_backups': config.get('global', 'max_backups')
    }
    
    # 确保全局备份路径以/结尾
    if not global_config['base_backup_path'].endswith('/'):
        global_config['base_backup_path'] += '/'
    
    # 收集所有要备份的数据库
    backup_tasks = []
    
    # 遍历所有数据库配置
    for section in config.sections():
        if not section.startswith('database:'):
            continue
            
        database_name = section.split(':', 1)[1]
        
        # 如果指定了数据库，则只处理该数据库
        if args.database and args.database != database_name:
            continue
            
        # 获取数据库配置
        db_config = dict(config.items(section))
        
        # 添加数据库名称到配置中
        if 'name' not in db_config:
            db_config['name'] = database_name
            
        # 将数据库备份任务添加到列表中
        backup_tasks.append({
            'db_config': db_config,
            'global_config': global_config
        })
    
    if not backup_tasks:
        logger.warning("没有找到符合条件的数据库备份任务")
        return
        
    logger.info(f"找到 {len(backup_tasks)} 个数据库备份任务")
    
    # 并行执行备份任务
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = []
        
        for task in backup_tasks:
            future = executor.submit(
                backup_database,
                task['db_config'],
                task['global_config']
            )
            futures.append(future)
            
        for future in as_completed(futures):
            success, database, error = future.result()
            if success:
                successful += 1
            else:
                failed += 1
                
    logger.info(f"所有数据库备份任务完成。成功: {successful}, 失败: {failed}")

if __name__ == "__main__":
    main() 