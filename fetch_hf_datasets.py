#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import configparser
from huggingface_hub import HfApi, logging as hf_logging

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("fetch_datasets.log")
    ]
)
logger = logging.getLogger("fetch_datasets")

# 禁用HuggingFace的详细日志
hf_logging.set_verbosity_error()

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='获取HuggingFace账号下的所有数据集')
    parser.add_argument('--token', required=True, help='HuggingFace API令牌')
    parser.add_argument('--username', required=True, help='HuggingFace用户名')
    parser.add_argument('--config', help='要更新的配置文件路径（如果不提供则只显示数据集列表）')
    parser.add_argument('--account-section', help='要更新的账号配置区段名称（例如：account:myaccount）')
    return parser.parse_args()

def get_user_datasets(token, username):
    """获取指定用户的所有数据集"""
    logger.info(f"正在获取用户 {username} 的数据集列表...")
    
    api = HfApi(token=token)
    
    try:
        # 获取用户的所有数据集
        datasets = api.list_datasets(author=username)
        logger.info(f"找到 {len(datasets)} 个数据集")
        
        # 返回数据集ID列表
        return [dataset.id for dataset in datasets]
    except Exception as e:
        logger.error(f"获取数据集列表时出错: {str(e)}")
        return []

def update_config_file(config_file, account_section, datasets):
    """更新配置文件中的数据集列表"""
    if not os.path.exists(config_file):
        logger.error(f"配置文件不存在: {config_file}")
        return False
        
    config = configparser.ConfigParser()
    config.read(config_file)
    
    if not config.has_section(account_section):
        logger.error(f"配置文件中不存在区段: {account_section}")
        return False
        
    # 更新数据集列表
    datasets_str = ", ".join(datasets)
    config.set(account_section, 'datasets', datasets_str)
    
    # 保存配置文件
    with open(config_file, 'w') as configfile:
        config.write(configfile)
        
    logger.info(f"已更新配置文件 {config_file} 中的数据集列表")
    return True

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 获取用户的数据集列表
    datasets = get_user_datasets(args.token, args.username)
    
    if not datasets:
        logger.warning(f"未找到用户 {args.username} 的数据集")
        return
        
    # 打印数据集列表
    print(f"用户 {args.username} 的数据集列表:")
    for i, dataset in enumerate(datasets, 1):
        print(f"{i}. {dataset}")
        
    # 如果提供了配置文件和账号区段，则更新配置文件
    if args.config and args.account_section:
        if update_config_file(args.config, args.account_section, datasets):
            print(f"已更新配置文件 {args.config} 中的数据集列表")
        else:
            print("更新配置文件失败")
    
if __name__ == "__main__":
    main() 