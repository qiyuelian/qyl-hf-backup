#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import configparser
import argparse
import subprocess
import logging

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backup_config.log")
    ]
)
logger = logging.getLogger("backup_config")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='从配置文件执行HuggingFace数据集备份')
    parser.add_argument('--config', default='config.ini', help='配置文件路径，默认为config.ini')
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

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 读取配置文件
    config = read_config(args.config)
    
    # 构建执行命令
    try:
        cmd = [
            sys.executable, 
            "hf_dataset_backup.py",
            "--hf-token", config.get('huggingface', 'token'),
            "--dataset", config.get('huggingface', 'dataset'),
            "--webdav-url", config.get('webdav', 'url'),
            "--webdav-username", config.get('webdav', 'username'),
            "--webdav-password", config.get('webdav', 'password'),
            "--webdav-path", config.get('webdav', 'path'),
            "--max-backups", config.get('backup', 'max_backups')
        ]
        
        logger.info("开始执行备份")
        subprocess.run(cmd, check=True)
        logger.info("备份完成")
    
    except configparser.NoSectionError as e:
        logger.error(f"配置文件缺少必要部分: {str(e)}")
        sys.exit(1)
    except configparser.NoOptionError as e:
        logger.error(f"配置文件缺少必要选项: {str(e)}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"备份过程中出错: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"发生未知错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 