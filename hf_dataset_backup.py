#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import tempfile
import shutil
import time
from datetime import datetime
import requests
from huggingface_hub import snapshot_download, HfApi
import webdav3.client as wc
from pathlib import Path

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("hf_backup.log")
    ]
)
logger = logging.getLogger("hf_backup")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='备份HuggingFace数据集到WebDAV网盘')
    parser.add_argument('--hf-token', required=True, help='HuggingFace API令牌')
    parser.add_argument('--dataset', required=True, help='要备份的数据集，格式为"用户名/数据集名称"')
    parser.add_argument('--webdav-url', required=True, help='WebDAV服务器URL')
    parser.add_argument('--webdav-username', required=True, help='WebDAV用户名')
    parser.add_argument('--webdav-password', required=True, help='WebDAV密码')
    parser.add_argument('--webdav-path', required=True, help='WebDAV保存路径，例如"/备份/huggingface/"')
    parser.add_argument('--max-backups', type=int, default=2, help='最多保留的备份数量，默认为2')
    
    return parser.parse_args()

def download_dataset(dataset_name, hf_token, temp_dir):
    """从HuggingFace下载数据集"""
    logger.info(f"开始下载数据集: {dataset_name}")
    try:
        # 下载数据集快照
        snapshot_path = snapshot_download(
            repo_id=dataset_name,
            repo_type="dataset",
            token=hf_token,
            local_dir=temp_dir,
            local_dir_use_symlinks=False
        )
        logger.info(f"数据集下载完成: {snapshot_path}")
        return snapshot_path
    except Exception as e:
        logger.error(f"下载数据集时出错: {str(e)}")
        raise

def create_archive(source_dir, dataset_name):
    """创建数据集的压缩文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_short_name = dataset_name.split('/')[-1]
    archive_name = f"{dataset_short_name}_{timestamp}.zip"
    archive_path = os.path.join(tempfile.gettempdir(), archive_name)
    
    logger.info(f"正在创建压缩文件: {archive_path}")
    shutil.make_archive(
        archive_path.replace('.zip', ''),  # 去掉.zip后缀，因为make_archive会自动添加
        'zip',
        source_dir
    )
    
    return archive_path + '.zip'  # 返回完整路径，包括.zip后缀

def setup_webdav_client(url, username, password):
    """设置WebDAV客户端"""
    options = {
        'webdav_hostname': url,
        'webdav_login': username,
        'webdav_password': password,
        'webdav_timeout': 300  # 5分钟超时
    }
    return wc.Client(options)

def upload_to_webdav(webdav_client, local_file, remote_path):
    """上传文件到WebDAV服务器"""
    logger.info(f"正在上传文件到WebDAV: {remote_path}")
    try:
        filename = os.path.basename(local_file)
        remote_file_path = remote_path + filename
        
        # 确保远程目录存在
        if not webdav_client.check(remote_path):
            webdav_client.mkdir(remote_path)
            
        # 上传文件
        webdav_client.upload_sync(
            remote_path=remote_file_path,
            local_path=local_file
        )
        logger.info(f"文件上传成功: {remote_file_path}")
        return remote_file_path
    except Exception as e:
        logger.error(f"上传文件时出错: {str(e)}")
        raise

def cleanup_old_backups(webdav_client, remote_path, dataset_name, max_backups):
    """清理旧的备份文件，只保留指定数量的最新备份"""
    dataset_short_name = dataset_name.split('/')[-1]
    logger.info(f"清理旧的备份文件，保留最新的{max_backups}个备份")
    
    try:
        # 列出远程目录中的所有文件
        files = webdav_client.list(remote_path)
        
        # 过滤出与当前数据集相关的备份文件
        backup_files = [f for f in files if f.startswith(dataset_short_name) and f.endswith('.zip')]
        
        if len(backup_files) <= max_backups:
            logger.info(f"备份文件数量未超过限制({len(backup_files)}/{max_backups})，无需清理")
            return
            
        # 按文件名排序（包含时间戳，所以旧文件会排在前面）
        backup_files.sort()
        
        # 确定需要删除的文件数量
        files_to_delete = len(backup_files) - max_backups
        
        # 删除旧文件
        for i in range(files_to_delete):
            file_to_delete = remote_path + backup_files[i]
            logger.info(f"删除旧备份文件: {file_to_delete}")
            webdav_client.clean(file_to_delete)
            
        logger.info(f"清理完成，已删除{files_to_delete}个旧备份文件")
    except Exception as e:
        logger.error(f"清理旧备份文件时出错: {str(e)}")
        raise

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    logger.info(f"创建临时目录: {temp_dir}")
    
    try:
        # 下载数据集
        dataset_path = download_dataset(args.dataset, args.hf_token, temp_dir)
        
        # 创建压缩文件
        archive_path = create_archive(dataset_path, args.dataset)
        
        # 设置WebDAV客户端
        webdav_client = setup_webdav_client(
            args.webdav_url,
            args.webdav_username,
            args.webdav_password
        )
        
        # 确保WebDAV路径以/结尾
        webdav_path = args.webdav_path
        if not webdav_path.endswith('/'):
            webdav_path += '/'
            
        # 上传文件到WebDAV
        upload_to_webdav(webdav_client, archive_path, webdav_path)
        
        # 清理旧的备份文件
        cleanup_old_backups(webdav_client, webdav_path, args.dataset, args.max_backups)
        
        logger.info("备份过程完成")
        
    except Exception as e:
        logger.error(f"备份过程中发生错误: {str(e)}")
        sys.exit(1)
    finally:
        # 清理临时文件
        logger.info(f"清理临时目录: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # 尝试删除临时压缩文件
        try:
            if 'archive_path' in locals() and os.path.exists(archive_path):
                os.remove(archive_path)
                logger.info(f"删除临时压缩文件: {archive_path}")
        except Exception as e:
            logger.warning(f"删除临时压缩文件时出错: {str(e)}")

if __name__ == "__main__":
    main() 