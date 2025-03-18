#!/bin/bash

# 全面备份定时任务设置脚本

# 获取当前脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 检查是否已安装所需的Python包
echo "检查并安装必要的依赖..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

# 确保所有脚本具有执行权限
chmod +x "$SCRIPT_DIR/hf_dataset_backup.py"
chmod +x "$SCRIPT_DIR/multi_accounts_backup.py"
chmod +x "$SCRIPT_DIR/fetch_hf_datasets.py"
chmod +x "$SCRIPT_DIR/db_backup.py"
chmod +x "$SCRIPT_DIR/multi_db_backup.py"
chmod +x "$SCRIPT_DIR/backup_all.py"

# 设置cron任务，每天凌晨2点运行全面备份
BACKUP_ALL_CRON_JOB="0 2 * * * cd $SCRIPT_DIR && python3 $SCRIPT_DIR/backup_all.py --hf-parallel 3 --db-parallel 2 >> $SCRIPT_DIR/backup_all_cron.log 2>&1"

# 检查crontab中是否已存在类似的任务
EXISTING_BACKUP_ALL_CRON=$(crontab -l 2>/dev/null | grep "backup_all.py")

if [ -z "$EXISTING_BACKUP_ALL_CRON" ]; then
    # 添加到现有的crontab
    (crontab -l 2>/dev/null; echo "$BACKUP_ALL_CRON_JOB") | crontab -
    echo "已设置全面备份定时任务：每天凌晨2点运行"
else
    echo "全面备份定时任务已存在，跳过设置"
fi

# 检查必要的数据库工具
echo "检查数据库工具..."

# 检查MySQL工具
if command -v mysqldump &>/dev/null; then
    echo "MySQL工具已安装"
else
    echo "警告：未找到mysqldump工具，MySQL数据库备份可能无法正常工作"
    echo "您可以通过安装MySQL客户端来解决此问题"
fi

# 检查PostgreSQL工具
if command -v pg_dump &>/dev/null; then
    echo "PostgreSQL工具已安装"
else
    echo "警告：未找到pg_dump工具，PostgreSQL数据库备份可能无法正常工作"
    echo "您可以通过安装PostgreSQL客户端来解决此问题"
fi

# 检查MongoDB工具
if command -v mongodump &>/dev/null; then
    echo "MongoDB工具已安装"
else
    echo "警告：未找到mongodump工具，MongoDB数据库备份可能无法正常工作"
    echo "您可以通过安装MongoDB客户端来解决此问题"
fi

# 检查IPv6网络配置
echo "检查IPv6网络连接..."
if ping6 -c 1 ipv6.google.com >/dev/null 2>&1; then
    echo "IPv6网络连接正常"
else
    echo "警告：无法通过IPv6连接到互联网，请检查您的网络配置"
    echo "确保您的服务器已正确配置IPv6"
fi

echo "设置完成！您可以使用以下命令手动测试全面备份："
echo "python3 $SCRIPT_DIR/backup_all.py"
echo ""
echo "您可以使用以下选项来自定义备份行为："
echo "  --hf-only：只备份HuggingFace数据集"
echo "  --db-only：只备份数据库"
echo "  --account [ACCOUNT]：只备份指定HuggingFace账号的数据集"
echo "  --dataset [DATASET]：只备份指定HuggingFace数据集"
echo "  --database [DATABASE]：只备份指定数据库"
echo ""
echo "您可以使用 'crontab -l' 命令查看当前的定时任务"
echo "您也可以使用 'crontab -e' 命令手动修改定时任务的运行频率"
echo ""
echo "备份日志将保存在 $SCRIPT_DIR/backup_all_cron.log 文件中" 