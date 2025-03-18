#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backup_all.log")
    ]
)
logger = logging.getLogger("backup_all")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='备份HuggingFace数据集和相关数据库到WebDAV网盘')
    parser.add_argument('--hf-config', default='multi_accounts_config.ini', help='HuggingFace数据集配置文件路径，默认为multi_accounts_config.ini')
    parser.add_argument('--db-config', default='db_config.ini', help='数据库配置文件路径，默认为db_config.ini')
    parser.add_argument('--hf-parallel', type=int, default=3, help='并行备份的数据集数量，默认为3')
    parser.add_argument('--db-parallel', type=int, default=2, help='并行备份的数据库数量，默认为2')
    parser.add_argument('--hf-only', action='store_true', help='只备份HuggingFace数据集')
    parser.add_argument('--db-only', action='store_true', help='只备份数据库')
    parser.add_argument('--account', help='只备份指定HuggingFace账号的数据集')
    parser.add_argument('--dataset', help='只备份指定HuggingFace数据集')
    parser.add_argument('--database', help='只备份指定数据库')
    return parser.parse_args()

def backup_huggingface_datasets(config_file, parallel=3, account=None, dataset=None):
    """备份HuggingFace数据集"""
    logger.info("开始备份HuggingFace数据集")
    
    # 构建备份命令
    cmd = [
        sys.executable, 
        "multi_accounts_backup.py",
        f"--config={config_file}",
        f"--parallel={parallel}"
    ]
    
    if account:
        cmd.append(f"--account={account}")
        
    if dataset:
        cmd.append(f"--dataset={dataset}")
    
    # 执行备份命令
    try:
        logger.info(f"执行HuggingFace数据集备份命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            logger.info("HuggingFace数据集备份成功")
            return True
        else:
            logger.error(f"HuggingFace数据集备份失败: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"执行HuggingFace数据集备份时发生错误: {str(e)}")
        return False

def backup_databases(config_file, parallel=2, database=None):
    """备份数据库"""
    logger.info("开始备份数据库")
    
    # 构建备份命令
    cmd = [
        sys.executable, 
        "multi_db_backup.py",
        f"--config={config_file}",
        f"--parallel={parallel}"
    ]
    
    if database:
        cmd.append(f"--database={database}")
    
    # 执行备份命令
    try:
        logger.info(f"执行数据库备份命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            logger.info("数据库备份成功")
            return True
        else:
            logger.error(f"数据库备份失败: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"执行数据库备份时发生错误: {str(e)}")
        return False

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 记录开始时间
    start_time = time.time()
    logger.info("开始全面备份过程")
    
    hf_success = True
    db_success = True
    
    # 备份HuggingFace数据集
    if not args.db_only:
        hf_success = backup_huggingface_datasets(
            args.hf_config, 
            args.hf_parallel,
            args.account,
            args.dataset
        )
    
    # 备份数据库
    if not args.hf_only:
        db_success = backup_databases(
            args.db_config,
            args.db_parallel,
            args.database
        )
    
    # 计算总耗时
    end_time = time.time()
    duration = end_time - start_time
    
    # 输出备份结果
    logger.info(f"备份过程完成，总耗时: {duration:.2f}秒")
    
    if not args.db_only:
        if hf_success:
            logger.info("HuggingFace数据集备份状态: 成功")
        else:
            logger.error("HuggingFace数据集备份状态: 失败")
    
    if not args.hf_only:
        if db_success:
            logger.info("数据库备份状态: 成功")
        else:
            logger.error("数据库备份状态: 失败")
    
    # 设置退出状态码
    if (not args.db_only and not hf_success) or (not args.hf_only and not db_success):
        sys.exit(1)

if __name__ == "__main__":
    main() 