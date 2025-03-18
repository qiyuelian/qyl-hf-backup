#!/bin/bash

# 多账号备份定时任务设置脚本

# 获取当前脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 检查是否已安装所需的Python包
echo "检查并安装必要的依赖..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

# 确保脚本具有执行权限
chmod +x "$SCRIPT_DIR/multi_accounts_backup.py"
chmod +x "$SCRIPT_DIR/hf_dataset_backup.py"
chmod +x "$SCRIPT_DIR/fetch_hf_datasets.py"

# 设置cron任务，每天凌晨3点运行多账号备份
CRON_JOB="0 3 * * * cd $SCRIPT_DIR && python3 $SCRIPT_DIR/multi_accounts_backup.py --config $SCRIPT_DIR/multi_accounts_config.ini --parallel 3 >> $SCRIPT_DIR/multi_accounts_cron.log 2>&1"

# 检查crontab中是否已存在类似的任务
EXISTING_CRON=$(crontab -l 2>/dev/null | grep "multi_accounts_backup.py")

if [ -z "$EXISTING_CRON" ]; then
    # 添加到现有的crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "已设置定时任务：每天凌晨3点运行多账号备份"
else
    echo "定时任务已存在，跳过设置"
fi

# 检查IPv6网络配置
echo "检查IPv6网络连接..."
if ping6 -c 1 ipv6.google.com >/dev/null 2>&1; then
    echo "IPv6网络连接正常"
else
    echo "警告：无法通过IPv6连接到互联网，请检查您的网络配置"
    echo "确保您的服务器已正确配置IPv6"
fi

echo "设置完成！您可以使用以下命令测试多账号备份："
echo "python3 $SCRIPT_DIR/multi_accounts_backup.py --config $SCRIPT_DIR/multi_accounts_config.ini"
echo ""
echo "您可以使用以下命令获取特定用户的数据集列表："
echo "python3 $SCRIPT_DIR/fetch_hf_datasets.py --token YOUR_TOKEN --username USERNAME"
echo ""
echo "要自动更新配置文件中的数据集列表，请使用："
echo "python3 $SCRIPT_DIR/fetch_hf_datasets.py --token YOUR_TOKEN --username USERNAME --config $SCRIPT_DIR/multi_accounts_config.ini --account-section account:ACCOUNT_NAME"
echo ""
echo "您可以使用 'crontab -l' 命令查看当前的定时任务"
echo "您也可以使用 'crontab -e' 命令手动修改定时任务的运行频率" 