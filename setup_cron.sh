#!/bin/bash

# 设置定时任务的脚本

# 获取当前脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 检查是否已安装所需的Python包
echo "检查并安装必要的依赖..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

# 设置cron任务，每天凌晨3点运行备份
CRON_JOB="0 3 * * * cd $SCRIPT_DIR && python3 $SCRIPT_DIR/backup_from_config.py --config $SCRIPT_DIR/config.ini >> $SCRIPT_DIR/cron_backup.log 2>&1"

# 检查crontab中是否已存在类似的任务
EXISTING_CRON=$(crontab -l 2>/dev/null | grep "backup_from_config.py")

if [ -z "$EXISTING_CRON" ]; then
    # 添加到现有的crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "已设置定时任务：每天凌晨3点运行备份"
else
    echo "定时任务已存在，跳过设置"
fi

echo "设置完成！您可以使用 'crontab -l' 命令查看当前的定时任务"
echo "您也可以手动修改定时任务的运行频率，方法是运行 'crontab -e' 命令"
echo ""
echo "计划的定时备份将在每天凌晨3点自动运行"
echo "您也可以通过运行以下命令手动触发备份："
echo "python3 $SCRIPT_DIR/backup_from_config.py" 