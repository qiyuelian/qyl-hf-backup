#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import tempfile
import shutil
import subprocess
import configparser
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
from huggingface_hub import snapshot_download, HfApi
import webdav3.client as wc

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backup.log")
    ]
)
logger = logging.getLogger("backup")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='备份HuggingFace项目和相关数据库到WebDAV网盘')
    parser.add_argument('--config', default='backup_config.ini', help='配置文件路径，默认为backup_config.ini')
    parser.add_argument('--parallel', type=int, default=3, help='并行备份任务数量，默认为3')
    parser.add_argument('--project', help='只备份指定项目，格式为"账号名/项目名"')
    parser.add_argument('--account', help='只备份指定账号的所有项目')
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

def setup_webdav_client(url, username, password):
    """设置WebDAV客户端"""
    options = {
        'webdav_hostname': url,
        'webdav_login': username,
        'webdav_password': password,
        'webdav_timeout': 300  # 5分钟超时
    }
    return wc.Client(options)

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
        return snapshot_path, True
    except Exception as e:
        logger.error(f"下载数据集 {dataset_name} 时出错: {str(e)}")
        return None, False

def create_archive(source_dir, project_name):
    """创建项目的压缩文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_short_name = project_name.split('/')[-1]
    archive_name = f"{project_short_name}_{timestamp}.zip"
    archive_path = os.path.join(tempfile.gettempdir(), archive_name)
    
    logger.info(f"正在创建压缩文件: {archive_path}")
    shutil.make_archive(
        archive_path.replace('.zip', ''),  # 去掉.zip后缀，因为make_archive会自动添加
        'zip',
        source_dir
    )
    
    return archive_path + '.zip'  # 返回完整路径，包括.zip后缀

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

def cleanup_old_backups(webdav_client, remote_path, project_name, max_backups):
    """清理旧的备份文件，只保留指定数量的最新备份"""
    project_short_name = project_name.split('/')[-1]
    logger.info(f"清理旧的备份文件，保留最新的{max_backups}个备份")
    
    try:
        # 列出远程目录中的所有文件
        files = webdav_client.list(remote_path)
        
        # 过滤出与当前项目相关的备份文件
        backup_files = [f for f in files if f.startswith(project_short_name) and f.endswith('.zip')]
        
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

def backup_mysql_database(db_config, temp_dir):
    """备份MySQL数据库"""
    db_name = db_config.get('db_name')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_name = f"{db_name}_{timestamp}.sql"
    backup_file_path = os.path.join(temp_dir, backup_file_name)
    
    logger.info(f"开始备份MySQL数据库: {db_name}")
    
    try:
        cmd = [
            'mysqldump',
            f"--user={db_config.get('db_user')}",
            f"--password={db_config.get('db_password')}",
            f"--host={db_config.get('db_host')}",
        ]
        
        if 'db_port' in db_config:
            cmd.append(f"--port={db_config.get('db_port')}")
            
        cmd.append('--single-transaction')
        cmd.append('--quick')
        cmd.append('--lock-tables=false')
        cmd.append(db_name)
        
        with open(backup_file_path, 'wb') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE)
            _, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"备份MySQL数据库失败: {stderr.decode('utf-8')}")
                return None
                
        logger.info(f"MySQL数据库备份成功: {backup_file_path}")
        return backup_file_path
            
    except Exception as e:
        logger.error(f"备份MySQL数据库出错: {str(e)}")
        return None

def backup_postgresql_database(db_config, temp_dir):
    """备份PostgreSQL数据库"""
    db_name = db_config.get('db_name')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_name = f"{db_name}_{timestamp}.dump"
    backup_file_path = os.path.join(temp_dir, backup_file_name)
    
    logger.info(f"开始备份PostgreSQL数据库: {db_name}")
    
    try:
        env = os.environ.copy()
        if 'db_password' in db_config:
            env['PGPASSWORD'] = db_config.get('db_password')
            
        cmd = ['pg_dump']
        
        if 'db_user' in db_config:
            cmd.append(f"--username={db_config.get('db_user')}")
            
        if 'db_host' in db_config:
            cmd.append(f"--host={db_config.get('db_host')}")
            
        if 'db_port' in db_config:
            cmd.append(f"--port={db_config.get('db_port')}")
            
        cmd.append('--format=custom')
        cmd.append(db_name)
        
        with open(backup_file_path, 'wb') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
            _, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"备份PostgreSQL数据库失败: {stderr.decode('utf-8')}")
                return None
                
        logger.info(f"PostgreSQL数据库备份成功: {backup_file_path}")
        return backup_file_path
            
    except Exception as e:
        logger.error(f"备份PostgreSQL数据库出错: {str(e)}")
        return None

def backup_mongodb_database(db_config, temp_dir):
    """备份MongoDB数据库"""
    db_name = db_config.get('db_name')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_name = f"{db_name}_{timestamp}.zip"
    backup_file_path = os.path.join(temp_dir, backup_file_name)
    
    logger.info(f"开始备份MongoDB数据库: {db_name}")
    
    try:
        dump_dir = tempfile.mkdtemp()
        
        cmd = ['mongodump', f'--db={db_name}', f'--out={dump_dir}']
        
        if 'db_user' in db_config and 'db_password' in db_config:
            cmd.append(f"--username={db_config.get('db_user')}")
            cmd.append(f"--password={db_config.get('db_password')}")
            cmd.append('--authenticationDatabase=admin')
            
        if 'db_host' in db_config:
            cmd.append(f"--host={db_config.get('db_host')}")
            
        if 'db_port' in db_config:
            cmd.append(f"--port={db_config.get('db_port')}")
            
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"备份MongoDB数据库失败: {stderr.decode('utf-8')}")
            shutil.rmtree(dump_dir, ignore_errors=True)
            return None
            
        # 创建压缩文件
        shutil.make_archive(
            backup_file_path.replace('.zip', ''),
            'zip',
            dump_dir
        )
        
        # 清理临时目录
        shutil.rmtree(dump_dir, ignore_errors=True)
        
        logger.info(f"MongoDB数据库备份成功: {backup_file_path}")
        return backup_file_path
            
    except Exception as e:
        logger.error(f"备份MongoDB数据库出错: {str(e)}")
        return None

def backup_sqlite_database(db_config, temp_dir):
    """备份SQLite数据库"""
    db_name = db_config.get('db_name')
    db_file = db_config.get('db_file')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_name = f"{db_name}_{timestamp}.db"
    backup_file_path = os.path.join(temp_dir, backup_file_name)
    
    logger.info(f"开始备份SQLite数据库: {db_file}")
    
    try:
        if not os.path.exists(db_file):
            logger.error(f"SQLite数据库文件不存在: {db_file}")
            return None
            
        # 直接复制数据库文件
        shutil.copy2(db_file, backup_file_path)
        
        logger.info(f"SQLite数据库备份成功: {backup_file_path}")
        return backup_file_path
            
    except Exception as e:
        logger.error(f"备份SQLite数据库出错: {str(e)}")
        return None

def backup_project(project_config, webdav_config):
    """备份单个项目及其关联的数据库"""
    project_name = project_config.get('name')
    account_name = project_name.split('/')[0]
    hf_token = project_config.get('hf_token')
    
    logger.info(f"开始备份项目: {project_name}")
    
    # 创建WebDAV客户端
    webdav_client = setup_webdav_client(
        webdav_config.get('url'),
        webdav_config.get('username'),
        webdav_config.get('password')
    )
    
    # 确定备份保存路径
    backup_path = project_config.get('backup_path', f"/backup/{account_name}/")
    if not backup_path.endswith('/'):
        backup_path += '/'
    
    # 设置最大备份数量
    max_backups = int(project_config.get('max_backups', 2))
    
    # 创建临时目录用于下载和处理文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 下载项目数据集
        dataset_path, success = download_dataset(project_name, hf_token, temp_dir)
        if not success:
            return project_name, False, "下载数据集失败"
        
        # 创建数据集压缩文件
        archive_path = create_archive(dataset_path, project_name)
        
        try:
            # 上传数据集压缩文件到WebDAV
            upload_to_webdav(webdav_client, archive_path, backup_path)
            
            # 清理旧的备份文件
            cleanup_old_backups(webdav_client, backup_path, project_name, max_backups)
            
            # 删除临时压缩文件
            if os.path.exists(archive_path):
                os.remove(archive_path)
                
            # 检查是否需要备份数据库
            if 'db_type' in project_config:
                db_backup_path = None
                db_type = project_config.get('db_type')
                
                # 根据数据库类型选择备份方法
                if db_type == 'mysql':
                    db_backup_path = backup_mysql_database(project_config, temp_dir)
                elif db_type == 'postgresql':
                    db_backup_path = backup_postgresql_database(project_config, temp_dir)
                elif db_type == 'mongodb':
                    db_backup_path = backup_mongodb_database(project_config, temp_dir)
                elif db_type == 'sqlite':
                    db_backup_path = backup_sqlite_database(project_config, temp_dir)
                
                # 如果数据库备份成功，上传到WebDAV
                if db_backup_path:
                    # 数据库备份保存路径可以与项目不同
                    db_backup_webdav_path = project_config.get('db_backup_path', backup_path)
                    if not db_backup_webdav_path.endswith('/'):
                        db_backup_webdav_path += '/'
                    
                    # 上传数据库备份文件
                    upload_to_webdav(webdav_client, db_backup_path, db_backup_webdav_path)
                    
                    # 清理旧的数据库备份文件
                    db_name = project_config.get('db_name')
                    cleanup_old_backups(webdav_client, db_backup_webdav_path, db_name, max_backups)
                    
                    # 删除临时数据库备份文件
                    if os.path.exists(db_backup_path):
                        os.remove(db_backup_path)
                else:
                    logger.warning(f"项目 {project_name} 的数据库备份失败")
            
            logger.info(f"项目 {project_name} 备份完成")
            return project_name, True, None
            
        except Exception as e:
            logger.error(f"备份项目 {project_name} 时发生错误: {str(e)}")
            return project_name, False, str(e)

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 读取配置文件
    config = read_config(args.config)
    
    # 获取WebDAV配置
    webdav_config = {
        'url': config.get('webdav', 'url'),
        'username': config.get('webdav', 'username'),
        'password': config.get('webdav', 'password')
    }
    
    # 收集所有要备份的项目
    projects_to_backup = []
    
    # 遍历所有账号的项目配置
    for section in config.sections():
        if not section.startswith('project:'):
            continue
            
        project_name = section.replace('project:', '')
        account_name = project_name.split('/')[0]
        
        # 如果指定了账号，则只处理该账号的项目
        if args.account and args.account != account_name:
            continue
            
        # 如果指定了项目，则只处理该项目
        if args.project and args.project != project_name:
            continue
            
        # 获取项目配置
        project_config = dict(config.items(section))
        project_config['name'] = project_name
        
        # 将项目添加到备份列表
        projects_to_backup.append(project_config)
    
    if not projects_to_backup:
        logger.warning("没有找到符合条件的项目需要备份")
        return
        
    logger.info(f"找到 {len(projects_to_backup)} 个项目需要备份")
    
    # 并行执行备份任务
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = []
        
        for project_config in projects_to_backup:
            future = executor.submit(
                backup_project,
                project_config,
                webdav_config
            )
            futures.append(future)
            
        for future in as_completed(futures):
            project_name, success, error = future.result()
            if success:
                successful += 1
                logger.info(f"项目 {project_name} 备份成功")
            else:
                failed += 1
                logger.error(f"项目 {project_name} 备份失败: {error}")
                
    logger.info(f"所有备份任务完成。成功: {successful}, 失败: {failed}")

if __name__ == "__main__":
    main() 