#!/bin/bash

# 数据库备份定时任务设置脚本

# 获取当前脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 检查是否已安装所需的Python包
echo "检查并安装必要的依赖..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

# 确保脚本具有执行权限
chmod +x "$SCRIPT_DIR/db_backup.py"
chmod +x "$SCRIPT_DIR/multi_db_backup.py"

# 设置cron任务，每天凌晨4点运行数据库备份
DB_CRON_JOB="0 4 * * * cd $SCRIPT_DIR && python3 $SCRIPT_DIR/multi_db_backup.py --config $SCRIPT_DIR/db_config.ini --parallel 2 >> $SCRIPT_DIR/db_backup_cron.log 2>&1"

# 检查crontab中是否已存在类似的任务
EXISTING_DB_CRON=$(crontab -l 2>/dev/null | grep "multi_db_backup.py")

if [ -z "$EXISTING_DB_CRON" ]; then
    # 添加到现有的crontab
    (crontab -l 2>/dev/null; echo "$DB_CRON_JOB") | crontab -
    echo "已设置数据库备份定时任务：每天凌晨4点运行"
else
    echo "数据库备份定时任务已存在，跳过设置"
fi

# 检查必要的数据库工具是否安装
echo "检查数据库工具..."

# 检查MySQL工具
if command -v mysqldump &>/dev/null; then
    echo "MySQL工具已安装"
else
    echo "警告：未找到mysqldump工具，MySQL数据库备份可能无法正常工作"
    echo "您可以通过安装MySQL客户端来解决此问题："
    echo "  Debian/Ubuntu: apt-get install mysql-client"
    echo "  CentOS/RHEL: yum install mysql"
fi

# 检查PostgreSQL工具
if command -v pg_dump &>/dev/null; then
    echo "PostgreSQL工具已安装"
else
    echo "警告：未找到pg_dump工具，PostgreSQL数据库备份可能无法正常工作"
    echo "您可以通过安装PostgreSQL客户端来解决此问题："
    echo "  Debian/Ubuntu: apt-get install postgresql-client"
    echo "  CentOS/RHEL: yum install postgresql"
fi

# 检查MongoDB工具
if command -v mongodump &>/dev/null; then
    echo "MongoDB工具已安装"
else
    echo "警告：未找到mongodump工具，MongoDB数据库备份可能无法正常工作"
    echo "您可以通过安装MongoDB客户端来解决此问题："
    echo "  Debian/Ubuntu: apt-get install mongodb-clients"
    echo "  CentOS/RHEL: yum install mongodb-org-tools"
fi

echo "设置完成！您可以使用以下命令测试数据库备份："
echo "python3 $SCRIPT_DIR/multi_db_backup.py --config $SCRIPT_DIR/db_config.ini"
echo ""
echo "您可以使用 'crontab -l' 命令查看当前的定时任务"
echo "您也可以使用 'crontab -e' 命令手动修改定时任务的运行频率"
echo ""
echo "备份日志将保存在 $SCRIPT_DIR/db_backup_cron.log 文件中" 