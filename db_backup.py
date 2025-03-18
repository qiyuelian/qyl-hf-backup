#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import tempfile
import shutil
import subprocess
import time
from datetime import datetime
import webdav3.client as wc
from pathlib import Path

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("db_backup.log")
    ]
)
logger = logging.getLogger("db_backup")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='备份数据库到WebDAV网盘')
    parser.add_argument('--db-type', required=True, choices=['mysql', 'postgresql', 'mongodb', 'sqlite', 'other'], 
                        help='数据库类型: mysql, postgresql, mongodb, sqlite, other')
    parser.add_argument('--db-name', required=True, help='数据库名称')
    parser.add_argument('--db-user', help='数据库用户名')
    parser.add_argument('--db-password', help='数据库密码')
    parser.add_argument('--db-host', help='数据库主机地址')
    parser.add_argument('--db-port', help='数据库端口')
    parser.add_argument('--db-file', help='SQLite数据库文件路径')
    parser.add_argument('--custom-cmd', help='自定义备份命令，当db-type为other时使用')
    parser.add_argument('--webdav-url', required=True, help='WebDAV服务器URL')
    parser.add_argument('--webdav-username', required=True, help='WebDAV用户名')
    parser.add_argument('--webdav-password', required=True, help='WebDAV密码')
    parser.add_argument('--webdav-path', required=True, help='WebDAV保存路径，例如"/备份/databases/"')
    parser.add_argument('--max-backups', type=int, default=2, help='最多保留的备份数量，默认为2')
    
    return parser.parse_args()

def backup_mysql(args, backup_file):
    """备份MySQL/MariaDB数据库"""
    logger.info(f"开始备份MySQL数据库: {args.db_name}")
    
    try:
        cmd = [
            'mysqldump',
            f'--user={args.db_user}',
            f'--password={args.db_password}',
            f'--host={args.db_host}',
        ]
        
        if args.db_port:
            cmd.append(f'--port={args.db_port}')
            
        cmd.append('--single-transaction')
        cmd.append('--quick')
        cmd.append('--lock-tables=false')
        cmd.append(args.db_name)
        
        with open(backup_file, 'wb') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE)
            _, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"备份MySQL数据库失败: {stderr.decode('utf-8')}")
                return False
                
        logger.info(f"MySQL数据库备份成功: {backup_file}")
        return True
            
    except Exception as e:
        logger.error(f"备份MySQL数据库出错: {str(e)}")
        return False

def backup_postgresql(args, backup_file):
    """备份PostgreSQL数据库"""
    logger.info(f"开始备份PostgreSQL数据库: {args.db_name}")
    
    try:
        env = os.environ.copy()
        if args.db_password:
            env['PGPASSWORD'] = args.db_password
            
        cmd = ['pg_dump']
        
        if args.db_user:
            cmd.append(f'--username={args.db_user}')
            
        if args.db_host:
            cmd.append(f'--host={args.db_host}')
            
        if args.db_port:
            cmd.append(f'--port={args.db_port}')
            
        cmd.append('--format=custom')
        cmd.append(args.db_name)
        
        with open(backup_file, 'wb') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
            _, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"备份PostgreSQL数据库失败: {stderr.decode('utf-8')}")
                return False
                
        logger.info(f"PostgreSQL数据库备份成功: {backup_file}")
        return True
            
    except Exception as e:
        logger.error(f"备份PostgreSQL数据库出错: {str(e)}")
        return False

def backup_mongodb(args, backup_file):
    """备份MongoDB数据库"""
    logger.info(f"开始备份MongoDB数据库: {args.db_name}")
    
    try:
        dump_dir = tempfile.mkdtemp()
        
        cmd = ['mongodump', f'--db={args.db_name}', f'--out={dump_dir}']
        
        if args.db_user and args.db_password:
            cmd.append(f'--username={args.db_user}')
            cmd.append(f'--password={args.db_password}')
            cmd.append('--authenticationDatabase=admin')
            
        if args.db_host:
            cmd.append(f'--host={args.db_host}')
            
        if args.db_port:
            cmd.append(f'--port={args.db_port}')
            
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"备份MongoDB数据库失败: {stderr.decode('utf-8')}")
            shutil.rmtree(dump_dir, ignore_errors=True)
            return False
            
        # 创建压缩文件
        shutil.make_archive(
            backup_file.replace('.zip', ''),
            'zip',
            dump_dir
        )
        
        # 清理临时目录
        shutil.rmtree(dump_dir, ignore_errors=True)
        
        logger.info(f"MongoDB数据库备份成功: {backup_file}")
        return True
            
    except Exception as e:
        logger.error(f"备份MongoDB数据库出错: {str(e)}")
        return False

def backup_sqlite(args, backup_file):
    """备份SQLite数据库"""
    logger.info(f"开始备份SQLite数据库: {args.db_file}")
    
    try:
        if not os.path.exists(args.db_file):
            logger.error(f"SQLite数据库文件不存在: {args.db_file}")
            return False
            
        # 直接复制数据库文件
        shutil.copy2(args.db_file, backup_file)
        
        logger.info(f"SQLite数据库备份成功: {backup_file}")
        return True
            
    except Exception as e:
        logger.error(f"备份SQLite数据库出错: {str(e)}")
        return False

def backup_other(args, backup_file):
    """使用自定义命令备份数据库"""
    logger.info(f"开始使用自定义命令备份数据库: {args.db_name}")
    
    if not args.custom_cmd:
        logger.error("备份类型为other时必须提供自定义命令")
        return False
        
    try:
        # 替换命令中的变量
        cmd = args.custom_cmd.replace('{backup_file}', backup_file)
        cmd = cmd.replace('{db_name}', args.db_name if args.db_name else '')
        cmd = cmd.replace('{db_user}', args.db_user if args.db_user else '')
        cmd = cmd.replace('{db_password}', args.db_password if args.db_password else '')
        cmd = cmd.replace('{db_host}', args.db_host if args.db_host else '')
        cmd = cmd.replace('{db_port}', args.db_port if args.db_port else '')
        
        # 执行命令
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"使用自定义命令备份数据库失败: {stderr.decode('utf-8')}")
            return False
            
        logger.info(f"数据库备份成功: {backup_file}")
        return True
            
    except Exception as e:
        logger.error(f"使用自定义命令备份数据库出错: {str(e)}")
        return False

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

def cleanup_old_backups(webdav_client, remote_path, db_name, max_backups):
    """清理旧的备份文件，只保留指定数量的最新备份"""
    logger.info(f"清理旧的备份文件，保留最新的{max_backups}个备份")
    
    try:
        # 列出远程目录中的所有文件
        files = webdav_client.list(remote_path)
        
        # 过滤出与当前数据库相关的备份文件
        backup_files = [f for f in files if f.startswith(db_name) and (f.endswith('.sql') or f.endswith('.dump') or f.endswith('.zip') or f.endswith('.db'))]
        
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
    
    # 确保WebDAV路径以/结尾
    webdav_path = args.webdav_path
    if not webdav_path.endswith('/'):
        webdav_path += '/'
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        backup_file_name = None
        backup_file_path = None
        
        if args.db_type == 'mysql':
            backup_file_name = f"{args.db_name}_{timestamp}.sql"
            backup_file_path = os.path.join(temp_dir, backup_file_name)
            success = backup_mysql(args, backup_file_path)
        elif args.db_type == 'postgresql':
            backup_file_name = f"{args.db_name}_{timestamp}.dump"
            backup_file_path = os.path.join(temp_dir, backup_file_name)
            success = backup_postgresql(args, backup_file_path)
        elif args.db_type == 'mongodb':
            backup_file_name = f"{args.db_name}_{timestamp}.zip"
            backup_file_path = os.path.join(temp_dir, backup_file_name)
            success = backup_mongodb(args, backup_file_path)
        elif args.db_type == 'sqlite':
            backup_file_name = f"{args.db_name}_{timestamp}.db"
            backup_file_path = os.path.join(temp_dir, backup_file_name)
            success = backup_sqlite(args, backup_file_path)
        elif args.db_type == 'other':
            backup_file_name = f"{args.db_name}_{timestamp}.backup"
            backup_file_path = os.path.join(temp_dir, backup_file_name)
            success = backup_other(args, backup_file_path)
        
        if not success:
            logger.error("数据库备份失败")
            sys.exit(1)
            
        try:
            # 设置WebDAV客户端
            webdav_client = setup_webdav_client(
                args.webdav_url,
                args.webdav_username,
                args.webdav_password
            )
            
            # 上传文件到WebDAV
            upload_to_webdav(webdav_client, backup_file_path, webdav_path)
            
            # 清理旧的备份文件
            cleanup_old_backups(webdav_client, webdav_path, args.db_name, args.max_backups)
            
            logger.info("备份过程完成")
            
        except Exception as e:
            logger.error(f"备份过程中发生错误: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    main() 