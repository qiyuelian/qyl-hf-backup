# HuggingFace项目备份工具 (简化版)

这是一个简单的工具，用于将HuggingFace上的项目和相关数据库备份到支持WebDAV的网盘中。

## 主要特点

- 支持备份多个HuggingFace账号下的多个项目
- 自动备份与项目关联的数据库（MySQL、PostgreSQL、MongoDB、SQLite）
- 支持自定义备份保存路径
- 可设置最大备份保留数量
- 支持并行备份多个项目
- 完全兼容IPv6环境
- 可设置为定时任务自动运行

## 系统要求

- Python 3.6+
- Linux/Unix系统（对于定时任务功能）
- 网络连接（IPv6环境完全兼容）
- 根据数据库类型，需要安装相应的客户端工具

## 快速开始

### 1. 安装依赖

```bash
pip install huggingface-hub webdavclient3 requests configparser pathlib
```

如果需要备份数据库，请安装相应的数据库客户端工具：

```bash
# MySQL 
apt-get install mysql-client  # Debian/Ubuntu
yum install mysql  # CentOS/RHEL

# PostgreSQL
apt-get install postgresql-client  # Debian/Ubuntu
yum install postgresql  # CentOS/RHEL

# MongoDB
apt-get install mongodb-clients  # Debian/Ubuntu
yum install mongodb-org-tools  # CentOS/RHEL
```

### 2. 配置

编辑 `backup_config.ini` 文件，配置WebDAV网盘信息和您的HuggingFace项目：

```ini
[webdav]
# WebDAV网盘配置
url = https://your-webdav-url.com
username = your_webdav_username
password = your_webdav_password

# 项目配置示例 - 不带数据库的项目
[project:account1/project1]
hf_token = account1_token_here
backup_path = /backup/account1/project1/
max_backups = 2

# 项目配置示例 - 带MySQL数据库的项目
[project:account1/project2]
hf_token = account1_token_here
backup_path = /backup/account1/project2/
# 数据库配置
db_type = mysql
db_name = project2_db
db_user = mysql_user
db_password = mysql_password
db_host = localhost
db_port = 3306
db_backup_path = /backup/account1/project2/db/
```

对于每个HuggingFace项目，您需要创建一个单独的配置部分，格式为 `[project:账号名/项目名]`。

### 3. 运行备份

手动运行备份：

```bash
python simple_backup.py
```

您可以使用以下选项来自定义备份行为：

```bash
# 只备份特定项目
python simple_backup.py --project account1/project1

# 只备份特定账号的所有项目
python simple_backup.py --account account1

# 设置并行备份任务数量
python simple_backup.py --parallel 5
```

### 4. 设置定时任务

使用提供的脚本设置定时任务：

```bash
chmod +x setup_backup_cron.sh
./setup_backup_cron.sh
```

这将设置一个每天凌晨3点自动运行的备份任务。

## 配置文件详解

### WebDAV配置

```ini
[webdav]
url = https://your-webdav-url.com
username = your_webdav_username
password = your_webdav_password
```

### 项目配置

基本配置（不带数据库）：

```ini
[project:account1/project1]
hf_token = account1_token_here          # HuggingFace API令牌
backup_path = /backup/account1/project1/ # 备份保存路径
max_backups = 2                          # 保留的备份数量
```

带MySQL数据库的项目：

```ini
[project:account1/project2]
hf_token = account1_token_here
backup_path = /backup/account1/project2/
db_type = mysql                          # 数据库类型
db_name = project2_db                    # 数据库名称
db_user = mysql_user                     # 数据库用户名
db_password = mysql_password             # 数据库密码
db_host = localhost                      # 数据库主机
db_port = 3306                           # 数据库端口
db_backup_path = /backup/db/project2/    # 数据库备份保存路径（可选）
```

其他支持的数据库类型：
- `postgresql`
- `mongodb`
- `sqlite` (需要额外提供 `db_file` 参数指定数据库文件路径)

## 日志

备份过程的日志保存在以下文件中：

- `backup.log` - 备份脚本的详细日志
- `backup_cron.log` - 定时任务运行的日志

## 备份文件格式

- 项目备份以ZIP格式保存，文件名格式为：`项目名_时间戳.zip`
- 数据库备份格式取决于数据库类型：
  - MySQL: SQL文件 (.sql)
  - PostgreSQL: 自定义转储格式 (.dump)
  - MongoDB: ZIP压缩文件 (.zip)
  - SQLite: 数据库文件 (.db)

## 注意事项

- 确保您的WebDAV服务支持大文件上传
- 对于很大的项目或数据库，备份过程可能需要较长时间
- 如果您有很多项目，建议调整并行备份数量以避免资源占用过高
- 在纯IPv6环境中使用时，确保您的WebDAV服务支持IPv6连接 