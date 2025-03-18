#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import configparser
import argparse
import logging
import tempfile
import shutil
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
        logging.FileHandler("multi_accounts_backup.log")
    ]
)
logger = logging.getLogger("multi_accounts_backup")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='备份多个HuggingFace账号的数据集到WebDAV网盘')
    parser.add_argument('--config', default='multi_accounts_config.ini', help='配置文件路径，默认为multi_accounts_config.ini')
    parser.add_argument('--parallel', type=int, default=3, help='并行备份的数据集数量，默认为3')
    parser.add_argument('--account', help='只备份指定账号的数据集，不指定则备份所有账号')
    parser.add_argument('--dataset', help='只备份指定数据集，不指定则备份账号下所有数据集')
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

def backup_dataset(hf_token, dataset_name, webdav_url, webdav_username, webdav_password, webdav_path, max_backups):
    """备份单个数据集"""
    logger.info(f"开始备份数据集: {dataset_name}")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 构建备份命令
            cmd = [
                sys.executable, 
                "hf_dataset_backup.py",
                "--hf-token", hf_token,
                "--dataset", dataset_name,
                "--webdav-url", webdav_url,
                "--webdav-username", webdav_username,
                "--webdav-password", webdav_password,
                "--webdav-path", webdav_path,
                "--max-backups", str(max_backups)
            ]
            
            # 执行备份命令
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                logger.info(f"数据集 {dataset_name} 备份成功")
                return True, dataset_name, None
            else:
                logger.error(f"数据集 {dataset_name} 备份失败: {result.stderr}")
                return False, dataset_name, result.stderr
        
        except Exception as e:
            logger.error(f"备份数据集 {dataset_name} 时发生错误: {str(e)}")
            return False, dataset_name, str(e)

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
    
    # 收集所有要备份的账号和数据集
    backup_tasks = []
    
    # 遍历所有账号配置
    for section in config.sections():
        if not section.startswith('account:'):
            continue
            
        account_name = section.split(':', 1)[1]
        
        # 如果指定了账号，则只处理该账号
        if args.account and args.account != account_name:
            continue
            
        # 获取账号配置
        hf_token = config.get(section, 'hf_token')
        
        # 获取该账号下的所有数据集
        datasets_str = config.get(section, 'datasets')
        datasets = [ds.strip() for ds in datasets_str.split(',')]
        
        # 如果指定了数据集，则只处理该数据集
        if args.dataset:
            datasets = [ds for ds in datasets if ds == args.dataset or ds.endswith('/' + args.dataset)]
            if not datasets:
                continue
                
        # 获取该账号的备份路径，如果没有设置则使用全局设置
        if config.has_option(section, 'backup_path'):
            backup_path = config.get(section, 'backup_path')
            if not backup_path.endswith('/'):
                backup_path += '/'
        else:
            backup_path = global_config['base_backup_path'] + account_name + '/'
            
        # 获取该账号的最大备份数量，如果没有设置则使用全局设置
        if config.has_option(section, 'max_backups'):
            max_backups = config.get(section, 'max_backups')
        else:
            max_backups = global_config['max_backups']
            
        # 将每个数据集的备份任务添加到列表中
        for dataset in datasets:
            backup_tasks.append({
                'account': account_name,
                'dataset': dataset,
                'hf_token': hf_token,
                'webdav_url': global_config['webdav_url'],
                'webdav_username': global_config['webdav_username'],
                'webdav_password': global_config['webdav_password'],
                'webdav_path': backup_path,
                'max_backups': max_backups
            })
    
    if not backup_tasks:
        logger.warning("没有找到符合条件的备份任务")
        return
        
    logger.info(f"找到 {len(backup_tasks)} 个备份任务")
    
    # 并行执行备份任务
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = []
        
        for task in backup_tasks:
            future = executor.submit(
                backup_dataset,
                task['hf_token'],
                task['dataset'],
                task['webdav_url'],
                task['webdav_username'],
                task['webdav_password'],
                task['webdav_path'],
                task['max_backups']
            )
            futures.append(future)
            
        for future in as_completed(futures):
            success, dataset, error = future.result()
            if success:
                successful += 1
            else:
                failed += 1
                
    logger.info(f"所有备份任务完成。成功: {successful}, 失败: {failed}")

if __name__ == "__main__":
    main() 