# HuggingFace数据集备份工具

这是一个简单的工具，用于将HuggingFace上的数据集和相关数据库备份到支持WebDAV的网盘中。它支持以下功能：

- 通过HuggingFace API下载指定的数据集
- 将数据集备份到WebDAV网盘
- 备份与HuggingFace项目关联的各种类型的数据库
- 自定义保存路径
- 仅保留最新的N个备份（默认为2个）
- 可设置为定时任务自动运行
- **支持多账号多数据集的备份管理**

## 系统要求

- Python 3.6+
- Linux/Unix系统（对于定时任务功能）
- 网络连接（IPv6环境完全兼容）
- 根据需要备份的数据库类型，可能需要安装相关的客户端工具

## 安装

1. 下载或克隆本仓库到您的服务器
2. 安装所需的依赖：

```bash
pip install -r requirements.txt
```

## 配置

### 单账号配置

编辑`config.ini`文件，填入您的HuggingFace token、要备份的数据集ID以及WebDAV信息：

```ini
[huggingface]
token = your_hf_token_here
dataset = username/dataset_name

[webdav]
url = https://your-webdav-url.com
username = your_webdav_username
password = your_webdav_password
path = /backup/huggingface/

[backup]
max_backups = 2
```

### 多账号配置

对于多账号配置，使用`multi_accounts_config.ini`文件：

```ini
[global]
# 全局设置
webdav_url = https://your-webdav-url.com
webdav_username = your_webdav_username
webdav_password = your_webdav_password
base_backup_path = /backup/huggingface/
max_backups = 2

# 账号1的配置
[account:account1]
hf_token = account1_token_here
# 账号1下的数据集列表
datasets = account1/dataset1, account1/dataset2, account1/dataset3
# 可选：自定义该账号的备份路径，如果不设置则使用全局设置
backup_path = /backup/account1/

# 账号2的配置
[account:account2]
hf_token = account2_token_here
datasets = account2/dataset1, account2/dataset2

# 账号3的配置
[account:account3]
hf_token = account3_token_here
datasets = account3/dataset1
# 可选：为该账号设置不同的备份数量
max_backups = 3
```

### 数据库备份配置

对于数据库备份，使用`db_config.ini`文件：

```ini
[global]
# WebDAV配置
webdav_url = https://your-webdav-url.com
webdav_username = your_webdav_username
webdav_password = your_webdav_password
base_backup_path = /backup/databases/
max_backups = 2

# MySQL数据库配置
[database:mysql_example]
type = mysql
name = my_database
user = mysql_user
password = mysql_password
host = localhost
port = 3306
backup_path = /backup/databases/mysql/

# PostgreSQL数据库配置
[database:postgresql_example]
type = postgresql
name = pg_database
user = pg_user
password = pg_password
host = localhost
port = 5432

# MongoDB数据库配置
[database:mongodb_example]
type = mongodb
name = mongo_db
user = mongo_user
password = mongo_password
host = localhost
port = 27017

# SQLite数据库配置
[database:sqlite_example]
type = sqlite
name = sqlite_db
file = /path/to/sqlite/database.db
```

## 使用方法

### 手动运行单账号备份

您可以通过以下命令手动运行单账号备份：

```bash
python backup_from_config.py
```

或者使用命令行参数指定配置文件：

```bash
python backup_from_config.py --config my_config.ini
```

### 手动运行多账号备份

使用多账号备份脚本：

```bash
python multi_accounts_backup.py
```

您可以指定只备份特定账号的数据集：

```bash
python multi_accounts_backup.py --account account1
```

或者只备份特定数据集：

```bash
python multi_accounts_backup.py --dataset dataset1
```

您还可以设置并行备份的数量：

```bash
python multi_accounts_backup.py --parallel 5
```

### 自动获取HuggingFace用户的数据集列表

使用`fetch_hf_datasets.py`脚本获取特定用户的所有数据集列表：

```bash
python fetch_hf_datasets.py --token YOUR_TOKEN --username USERNAME
```

您还可以自动更新配置文件中的数据集列表：

```bash
python fetch_hf_datasets.py --token YOUR_TOKEN --username USERNAME --config multi_accounts_config.ini --account-section account:account1
```

### 手动运行数据库备份

您可以使用以下命令手动备份单个数据库：

```bash
python db_backup.py --db-type mysql --db-name mydatabase --db-user user --db-password pass --db-host localhost --webdav-url https://webdav.com --webdav-username user --webdav-password pass --webdav-path /backup/db/
```

使用配置文件备份多个数据库：

```bash
python multi_db_backup.py
```

您可以指定只备份特定数据库：

```bash
python multi_db_backup.py --database mysql_example
```

您还可以设置并行备份的数量：

```bash
python multi_db_backup.py --parallel 3
```

### 直接使用主脚本

您也可以直接使用主脚本，通过命令行参数提供所有信息：

```bash
python hf_dataset_backup.py \
  --hf-token YOUR_HF_TOKEN \
  --dataset username/dataset_name \
  --webdav-url https://your-webdav-url.com \
  --webdav-username your_webdav_username \
  --webdav-password your_webdav_password \
  --webdav-path /backup/huggingface/ \
  --max-backups 2
```

### 设置定时任务

#### 单账号定时任务

在Linux系统上，您可以运行以下脚本设置每天自动运行的单账号定时任务：

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

#### 多账号定时任务

设置多账号定时备份任务：

```bash
chmod +x setup_multi_accounts_cron.sh
./setup_multi_accounts_cron.sh
```

#### 数据库定时备份任务

设置数据库定时备份任务：

```bash
chmod +x setup_db_backup_cron.sh
./setup_db_backup_cron.sh
```

默认情况下，数据集备份将在每天凌晨3点自动运行，数据库备份将在每天凌晨4点自动运行。您可以通过编辑脚本文件或使用`crontab -e`命令修改运行频率。

## 日志

脚本运行时会生成以下日志文件：

- `hf_backup.log`：单账号主备份脚本的日志
- `backup_config.log`：单账号配置文件脚本的日志
- `cron_backup.log`：单账号定时任务运行的日志
- `multi_accounts_backup.log`：多账号备份脚本的日志
- `multi_accounts_cron.log`：多账号定时任务运行的日志
- `fetch_datasets.log`：获取数据集脚本的日志
- `db_backup.log`：数据库备份脚本的日志
- `multi_db_backup.log`：多数据库备份脚本的日志
- `db_backup_cron.log`：数据库备份定时任务的日志

## 支持的数据库类型

本工具支持以下类型的数据库备份：

1. **MySQL/MariaDB** - 使用 `mysqldump` 工具
2. **PostgreSQL** - 使用 `pg_dump` 工具
3. **MongoDB** - 使用 `mongodump` 工具
4. **SQLite** - 直接复制数据库文件
5. **自定义** - 通过提供自定义备份命令支持其他类型的数据库

## 纯IPv6环境说明

本工具完全兼容纯IPv6环境。在纯IPv6服务器上使用时，请确保：

1. 您的服务器已正确配置IPv6网络
2. 您使用的WebDAV服务支持IPv6连接
3. HuggingFace API可以通过IPv6访问（目前支持）
4. 您的数据库服务器支持IPv6连接

`setup_multi_accounts_cron.sh`脚本包含了IPv6连接检测，可以帮助您验证服务器的IPv6连接状态。

## 注意事项

- 请确保您的WebDAV服务支持大文件上传（部分数据集或数据库备份可能很大）
- 对于非常大的数据集或数据库，可能需要更长的处理时间
- 备份会以合适的格式保存（数据集为zip，数据库根据类型有不同格式）
- 确保您的服务器有足够的临时存储空间来处理数据集下载和压缩
- 如果您有多个账号和多个数据集，建议适当控制并行备份数量，以避免服务器资源占用过高
- 数据库备份需要安装相应的客户端工具（例如备份MySQL需要安装mysqldump） 