#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import tempfile
import shutil
import time
import tarfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import configparser
import subprocess
from pathlib import Path
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

def download_dataset(dataset_name, hf_token, temp_dir, repo_type=None):
    """从HuggingFace下载数据集"""
    logger.info(f"开始下载数据集: {dataset_name}")
    
    try:
        # 创建HuggingFace API对象
        api = HfApi(token=hf_token)
        
        # 如果指定了存储库类型，则直接使用
        if repo_type:
            logger.info(f"使用配置的存储库类型: {repo_type}")
            repo_types = [repo_type]
        else:
            # 否则尝试不同的存储库类型
            logger.info("未指定存储库类型，将尝试多种类型")
            repo_types = ["dataset", "model", "space"]
            
        success = False
        
        for rt in repo_types:
            try:
                logger.info(f"尝试以 {rt} 类型访问存储库: {dataset_name}")
                # 尝试列出存储库文件
                files = api.list_repo_files(dataset_name, repo_type=rt)
                success = True
                repo_type = rt  # 保存成功的类型
                logger.info(f"成功以 {rt} 类型访问存储库")
                break
            except Exception as e:
                logger.warning(f"无法以 {rt} 类型访问: {str(e)}")
                continue
                
        if not success:
            raise Exception(f"无法访问存储库 {dataset_name}，尝试了所有支持的类型")
        
        # 查找可能的备份文件（压缩包）
        backup_files = [f for f in files if f.endswith('.zip') or f.endswith('.tar.gz') or f.endswith('.7z')]
        
        if backup_files:
            # 排序获取最新的备份文件
            backup_files.sort(reverse=True)
            latest_backup = backup_files[0]
            logger.info(f"发现{len(backup_files)}个备份文件，将下载最新的: {latest_backup}")
            
            # 下载最新的备份文件
            file_path = os.path.join(temp_dir, latest_backup)
            api.hf_hub_download(
                repo_id=dataset_name,
                filename=latest_backup,
                local_dir=temp_dir,
                local_dir_use_symlinks=False,
                repo_type=repo_type,
                token=hf_token
            )
            
            logger.info(f"最新备份文件下载完成: {file_path}")
            return file_path
        else:
            # 如果没有发现备份文件，下载整个数据集
            logger.info(f"未发现备份文件，将下载整个数据集")
            snapshot_path = snapshot_download(
                repo_id=dataset_name,
                repo_type=repo_type,
                token=hf_token,
                local_dir=temp_dir,
                local_dir_use_symlinks=False
            )
            logger.info(f"数据集下载完成: {snapshot_path}")
            return snapshot_path
    
    except Exception as e:
        logger.error(f"下载数据集时出错: {str(e)}")
        return None

def create_archive(source_dir, file_prefix):
    """创建数据集的压缩文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{file_prefix}_backup_{timestamp}.tar.gz"
    archive_path = os.path.join(tempfile.gettempdir(), archive_name)
    
    logger.info(f"正在创建压缩文件: {archive_path}")
    
    try:
        # 创建压缩文件
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))
            
        logger.info(f"压缩文件创建成功: {archive_path}")
        return archive_path
    except Exception as e:
        logger.error(f"创建压缩文件时出错: {str(e)}")
        return None

def upload_to_webdav(webdav_client, local_file, remote_path):
    """上传文件到WebDAV服务器"""
    logger.info(f"正在上传文件到WebDAV: {remote_path}")
    try:
        filename = os.path.basename(local_file)
        remote_file_path = remote_path + filename
        
        # 递归创建远程目录
        create_remote_dirs(webdav_client, remote_path)
            
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

def create_remote_dirs(webdav_client, path):
    """递归创建远程目录"""
    if path == "/" or path == "":
        return
        
    # 去掉末尾的斜杠以便处理
    if path.endswith('/'):
        path = path[:-1]
        
    parent_path = os.path.dirname(path)
    
    # 确保父目录存在
    if parent_path and parent_path != "/":
        create_remote_dirs(webdav_client, parent_path + "/")
    
    # 创建当前目录
    if not webdav_client.check(path + "/"):
        try:
            logger.info(f"创建远程目录: {path}/")
            webdav_client.mkdir(path + "/")
        except Exception as e:
            # 如果目录已存在，忽略错误
            logger.debug(f"创建目录时发生错误(可能已存在): {str(e)}")

def cleanup_old_backups(webdav_client, remote_path, name, max_backups, is_db=False, is_project=False):
    """清理旧的备份文件，只保留指定数量的最新备份"""
    prefix = name  # name已经是文件前缀或数据库名
    logger.info(f"清理旧的备份文件，保留最新的{max_backups}个备份")
    
    try:
        # 列出远程目录中的所有文件
        files = webdav_client.list(remote_path)
        logger.info(f"远程目录 {remote_path} 中的所有文件: {files}")
        
        # 为了处理各种情况，我们允许多个可能的前缀
        possible_prefixes = [prefix]
        
        # 特殊处理sjg/sillytavern情况
        if prefix == "sjg":
            possible_prefixes.append("sillytavern")
        elif prefix == "sillytavern":
            possible_prefixes.append("sjg")
            
        # 过滤出与当前项目/数据库相关的备份文件
        if is_db:
            # 数据库备份文件可能有多种格式
            backup_files = []
            for p in possible_prefixes:
                backup_files.extend([f for f in files if f.startswith(p) and 
                           (f.endswith('.sql') or f.endswith('.dump') or 
                            f.endswith('.zip') or f.endswith('.db'))])
        else:
            # 项目备份文件
            backup_files = []
            # 如果是项目备份并且我们知道确切的前缀，就使用更严格的匹配
            if is_project:
                for p in possible_prefixes:
                    backup_files.extend([f for f in files if 
                               (f.startswith(f"{p}_backup_") or  # 标准格式 prefix_backup_timestamp.ext
                                f.startswith(f"{p}_20"))  # 备用格式 prefix_timestamp.ext
                               and (f.endswith('.zip') or f.endswith('.tar.gz') or f.endswith('.7z'))])
            else:
                # 旧的简单匹配方式，仅作为后备
                for p in possible_prefixes:
                    backup_files.extend([f for f in files if f.startswith(p) and 
                               (f.endswith('.zip') or f.endswith('.tar.gz') or f.endswith('.7z'))])
        
        # 删除重复项
        backup_files = list(set(backup_files))
        
        logger.info(f"远程目录中找到 {len(backup_files)} 个备份文件: {backup_files}")
        
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
    """备份MySQL/MariaDB数据库"""
    db_name = db_config['db_name']
    db_user = db_config['db_user']
    db_password = db_config['db_password']
    db_host = db_config['db_host']
    db_port = db_config.get('db_port', '3306')
    
    logger.info(f"开始备份MySQL数据库: {db_name}")
    
    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(temp_dir, f"{db_name}_{timestamp}.sql")
    
    try:
        cmd = [
            'mysqldump',
            f'--user={db_user}',
            f'--password={db_password}',
            f'--host={db_host}',
            f'--port={db_port}',
            '--single-transaction',
            '--quick',
            '--lock-tables=false',
            db_name
        ]
        
        with open(backup_file, 'wb') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE)
            _, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"备份MySQL数据库失败: {stderr.decode('utf-8')}")
                return None
                
        logger.info(f"MySQL数据库备份成功: {backup_file}")
        return backup_file
            
    except Exception as e:
        logger.error(f"备份MySQL数据库出错: {str(e)}")
        return None

def backup_postgresql_database(db_config, temp_dir):
    """备份PostgreSQL数据库"""
    db_name = db_config['db_name']
    db_user = db_config['db_user']
    db_password = db_config['db_password']
    db_host = db_config['db_host']
    db_port = db_config.get('db_port', '5432')
    
    logger.info(f"开始备份PostgreSQL数据库: {db_name}")
    
    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(temp_dir, f"{db_name}_{timestamp}.dump")
    
    try:
        # 处理密码中的特殊字符
        # 在环境变量中设置密码，避免命令行参数的问题
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password.strip('"\'')  # 移除可能的引号
        
        # 使用环境变量启用SSL
        env['PGSSLMODE'] = 'require'  # 要求SSL连接
        
        cmd = [
            'pg_dump',
            f'--username={db_user}',
            f'--host={db_host}',
            f'--port={db_port}',
            '--format=custom',
            '--no-password',  # 不提示密码，从环境变量获取
            '--verbose',      # 显示详细信息
            '--no-owner',     # 不输出所有者命令
            '--no-acl',       # 不输出访问权限命令
            '--compress=9',   # 最高压缩级别
            db_name
        ]
        
        logger.info(f"执行PostgreSQL备份命令: {' '.join(cmd)}")
        
        # 捕获标准输出和错误
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"备份PostgreSQL数据库失败: {stderr.decode('utf-8')}")
            return None
            
        # 将输出写入文件
        with open(backup_file, 'wb') as f:
            f.write(stdout)
                
        logger.info(f"PostgreSQL数据库备份成功: {backup_file}")
        return backup_file
            
    except Exception as e:
        logger.error(f"备份PostgreSQL数据库出错: {str(e)}")
        return None

def backup_mongodb_database(db_config, temp_dir):
    """备份MongoDB数据库"""
    db_name = db_config['db_name']
    db_user = db_config.get('db_user')
    db_password = db_config.get('db_password')
    db_host = db_config.get('db_host', 'localhost')
    db_port = db_config.get('db_port', '27017')
    
    logger.info(f"开始备份MongoDB数据库: {db_name}")
    
    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(temp_dir, f"{db_name}_{timestamp}.zip")
    
    try:
        dump_dir = tempfile.mkdtemp()
        
        cmd = ['mongodump', f'--db={db_name}', f'--out={dump_dir}']
        
        if db_user and db_password:
            cmd.append(f'--username={db_user}')
            cmd.append(f'--password={db_password}')
            cmd.append('--authenticationDatabase=admin')
            
        if db_host:
            cmd.append(f'--host={db_host}')
            
        if db_port:
            cmd.append(f'--port={db_port}')
            
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"备份MongoDB数据库失败: {stderr.decode('utf-8')}")
            shutil.rmtree(dump_dir, ignore_errors=True)
            return None
            
        # 创建压缩文件
        shutil.make_archive(
            backup_file.replace('.zip', ''),
            'zip',
            dump_dir
        )
        
        # 清理临时目录
        shutil.rmtree(dump_dir, ignore_errors=True)
        
        logger.info(f"MongoDB数据库备份成功: {backup_file}")
        return backup_file
            
    except Exception as e:
        logger.error(f"备份MongoDB数据库出错: {str(e)}")
        return None

def backup_sqlite_database(db_config, temp_dir):
    """备份SQLite数据库"""
    db_name = db_config['db_name']
    db_file = db_config['db_file']
    
    logger.info(f"开始备份SQLite数据库: {db_file}")
    
    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(temp_dir, f"{db_name}_{timestamp}.db")
    
    try:
        if not os.path.exists(db_file):
            logger.error(f"SQLite数据库文件不存在: {db_file}")
            return None
            
        # 直接复制数据库文件
        shutil.copy2(db_file, backup_file)
        
        logger.info(f"SQLite数据库备份成功: {backup_file}")
        return backup_file
            
    except Exception as e:
        logger.error(f"备份SQLite数据库出错: {str(e)}")
        return None

def backup_project(project_config, webdav_config):
    """备份单个项目"""
    project_name = project_config['project_name']
    hf_token = project_config['hf_token']
    backup_path = project_config['backup_path']
    max_backups = int(project_config.get('max_backups', 2))
    hf_type = project_config.get('hf_type', None)  # 从配置中获取存储库类型
    
    logger.info(f"开始备份项目: {project_name}")
    
    # 默认使用项目短名称作为文件前缀
    project_short_name = project_name.split('/')[-1]
    file_prefix = project_short_name
    
    # 存储检测到的真实文件前缀，用于后续清理
    detected_prefix = None
    
    try:
        # 创建WebDAV客户端
        webdav_client = setup_webdav_client(
            webdav_config['url'],
            webdav_config['username'],
            webdav_config['password']
        )
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 下载数据集，使用配置的存储库类型
            dataset_dir = download_dataset(project_name, hf_token, temp_dir, hf_type)
            
            # 如果数据集下载失败，但WebDAV已有备份，则可以跳过下载步骤
            if not dataset_dir:
                logger.warning(f"无法从HuggingFace下载项目 {project_name}，检查WebDAV是否已有备份")
                # 检查WebDAV中是否已有备份
                try:
                    remote_files = webdav_client.list(backup_path)
                    
                    # 尝试查找与项目相关的备份
                    backup_found = False
                    
                    # 特殊处理sjg/sillytavern情况
                    possible_prefixes = [project_short_name]
                    if project_short_name == 'sjg':
                        possible_prefixes.append('sillytavern')
                    
                    for prefix in possible_prefixes:
                        for f in remote_files:
                            if (f.startswith(f"{prefix}_backup_") or f.startswith(f"{prefix}_20")) and \
                               (f.endswith('.zip') or f.endswith('.tar.gz') or f.endswith('.7z')):
                                backup_found = True
                                detected_prefix = prefix
                                logger.info(f"在WebDAV中找到项目 {project_name} 的现有备份，使用前缀: {prefix}")
                                break
                        if backup_found:
                            break
                    
                    if backup_found:
                        logger.info(f"项目 {project_name} 已有备份，跳过下载和上传步骤")
                        # 仅进行清理
                        backup_prefix = detected_prefix if detected_prefix else project_short_name
                        cleanup_old_backups(webdav_client, backup_path, backup_prefix, max_backups, is_db=False, is_project=True)
                        
                        # 如果项目配置中有数据库，继续备份数据库
                        if 'db_type' in project_config:
                            goto_db_backup = True
                        else:
                            logger.info(f"项目 {project_name} 备份完成（使用现有备份）")
                            return True
                    else:
                        logger.error(f"无法从HuggingFace下载项目 {project_name}，且WebDAV中没有现有备份")
                        return False
                
                except Exception as e:
                    logger.error(f"检查WebDAV备份时出错: {str(e)}")
                    return False
            else:
                # 正常处理下载的数据集
                if os.path.isdir(dataset_dir):
                    # 创建压缩文件
                    logger.info(f"创建压缩文件: {file_prefix}")
                    archive_path = create_archive(dataset_dir, file_prefix)
                else:
                    # 使用已下载的压缩文件，并从文件名中提取前缀
                    basename = os.path.basename(dataset_dir)
                    logger.info(f"使用已下载的压缩文件: {basename}")
                    archive_path = dataset_dir
                    
                    # 从文件名中提取前缀，通常格式为 prefix_backup_timestamp.ext
                    parts = basename.split('_')
                    if len(parts) > 1:
                        # 提取前缀（可能是多个部分）
                        # 假设格式为 prefix_backup_timestamp.ext 或 prefix_timestamp.ext
                        if 'backup' in parts:
                            backup_index = parts.index('backup')
                            detected_prefix = '_'.join(parts[:backup_index])
                        else:
                            # 假设最后一部分是时间戳，前面都是前缀
                            detected_prefix = '_'.join(parts[:-1])
                        
                        logger.info(f"从文件名 {basename} 中检测到前缀: {detected_prefix}")
                    
                    # 如果无法提取前缀，使用默认前缀
                    if not detected_prefix:
                        # 根据经验处理特殊情况
                        if project_short_name == 'sjg':
                            detected_prefix = 'sillytavern'
                        else:
                            detected_prefix = project_short_name
                        logger.info(f"无法从文件名提取前缀，使用默认前缀: {detected_prefix}")
                
                # 上传文件到WebDAV
                upload_to_webdav(webdav_client, archive_path, backup_path)
                
                # 清理旧的备份文件
                # 使用检测到的前缀而不是项目名
                backup_prefix = detected_prefix if detected_prefix else project_short_name
                cleanup_old_backups(webdav_client, backup_path, backup_prefix, max_backups, is_db=False, is_project=True)
                
                # 设置一个标记，指示是否需要继续备份数据库
                goto_db_backup = 'db_type' in project_config
        
        # 如果有数据库配置，备份数据库
        if 'db_type' in project_config and ('goto_db_backup' not in locals() or goto_db_backup):
            db_type = project_config['db_type']
            db_name = project_config['db_name']
            db_backup_path = project_config.get('db_backup_path', backup_path + 'db/')
            
            logger.info(f"为项目 {project_name} 备份 {db_type} 数据库")
            db_backup_success = False
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 根据数据库类型备份
                if db_type == 'mysql':
                    db_file = backup_mysql_database(project_config, temp_dir)
                elif db_type == 'postgresql':
                    db_file = backup_postgresql_database(project_config, temp_dir)
                elif db_type == 'mongodb':
                    db_file = backup_mongodb_database(project_config, temp_dir)
                elif db_type == 'sqlite':
                    db_file = backup_sqlite_database(project_config, temp_dir)
                else:
                    logger.error(f"不支持的数据库类型: {db_type}")
                    db_file = None
                
                if db_file:
                    # 确保远程目录存在
                    create_remote_dirs(webdav_client, db_backup_path)
                    
                    # 上传数据库备份文件
                    upload_to_webdav(webdav_client, db_file, db_backup_path)
                    
                    # 清理旧的数据库备份文件
                    cleanup_old_backups(webdav_client, db_backup_path, db_name, max_backups, is_db=True, is_project=False)
                    
                    db_backup_success = True
                else:
                    logger.error(f"数据库备份失败")
                    
            if not db_backup_success:
                logger.error(f"项目 {project_name} 备份失败: 数据库备份失败")
                return False
        
        logger.info(f"项目 {project_name} 备份完成")
        return True
        
    except Exception as e:
        logger.error(f"备份项目 {project_name} 时发生错误: {str(e)}")
        return False

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 读取配置文件
    config = read_config(args.config)
    
    # 获取WebDAV配置
    webdav_config = dict(config.items('webdav'))
    logger.info("WebDAV配置已加载")
    
    # 获取所有项目配置
    projects = []
    
    for section in config.sections():
        if section.startswith('project:'):
            project_name = section.split(':', 1)[1]
            
            # 如果指定了项目，则只处理该项目
            if args.project and args.project != project_name:
                continue
                
            # 如果指定了账号，则只处理该账号的项目
            if args.account and not project_name.startswith(args.account + '/'):
                continue
                
            # 获取项目配置
            project_config = dict(config.items(section))
            project_config['project_name'] = project_name
            
            # 确保备份路径以/结尾
            if 'backup_path' in project_config and not project_config['backup_path'].endswith('/'):
                project_config['backup_path'] += '/'
                
            # 确保数据库备份路径以/结尾
            if 'db_backup_path' in project_config and not project_config['db_backup_path'].endswith('/'):
                project_config['db_backup_path'] += '/'
                
            projects.append(project_config)
    
    if not projects:
        if args.project:
            logger.error(f"找不到指定的项目: {args.project}")
        elif args.account:
            logger.error(f"找不到指定账号的项目: {args.account}")
        else:
            logger.error("配置文件中没有项目配置")
        return
        
    logger.info(f"找到 {len(projects)} 个项目需要备份")
    
    # 项目备份结果
    success_count = 0
    failure_count = 0
    
    # 备份项目
    for project_config in projects:
        result = backup_project(project_config, webdav_config)
        
        if result:
            logger.info(f"项目 {project_config['project_name']} 备份成功")
            success_count += 1
        else:
            logger.error(f"项目 {project_config['project_name']} 备份失败")
            failure_count += 1
    
    logger.info(f"所有备份任务完成。成功: {success_count}, 失败: {failure_count}")

if __name__ == "__main__":
    main() 