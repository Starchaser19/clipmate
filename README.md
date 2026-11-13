# ClipMate - Windows 剪贴板历史管理工具

个人 Windows 桌面剪贴板管理工具，解决系统只能保留最后一次复制内容的痛点。

## 功能

- 🔍 **历史记录** — 自动监听剪贴板，保存文本和图片历史
- ⚡ **增量刷新** — 新记录只追加卡片，不再每 2 秒重建整个列表
- 🧹 **自动清理** — 每天清理旧记录并回收空间，收藏和标签记录永久保留
- 📝 **文本复制** — 单击文本卡片复制到剪贴板
- 🖼️ **图片管理** — 左侧文本、右侧图片，双栏布局
- 👆 **双击预览** — 双击图片卡片用系统照片应用打开
- ⭐ **收藏置顶** — 常用内容收藏后优先显示
- 🏷️ **标签分类** — 创建标签，右键记录打标签
- 🔎 **搜索过滤** — 搜索历史内容，筛选收藏
- 📌 **系统托盘** — 关闭窗口最小化到托盘，后台持续监听
- 🚀 **开机自启** — 托盘菜单一键开启
- 🎨 **清新界面** — 无边框自定义标题栏，圆角投影，浅色主题

## 快速开始

### 运行

```bash
pip install -r requirements.txt
python main.py      # 有控制台，便于调试
pythonw main.py     # 无控制台，日常使用
```

关闭窗口只会隐藏到托盘，监听继续运行；退出请用托盘菜单。

### 打包为 exe

```bash
pip install pyinstaller
pyinstaller --noconfirm ClipMate.spec
# 输出: dist/ClipMate.exe
```

`ClipMate.spec` 已经包含图标和 `resources/icons`，不需要额外 `--add-data`。
`build/` 和 `dist/` 已被 `.gitignore` 忽略，不会提交到仓库。

## 项目结构

```
clipmate/
├── main.py                     # 入口
├── requirements.txt            # 依赖清单
├── ClipMate.spec               # PyInstaller 配置
├── README.md
├── app/
│   ├── database.py             # SQLite 数据库层
│   ├── monitor.py              # 剪贴板监听线程
│   ├── maintenance.py          # 每日清理旧记录 + VACUUM
│   ├── autostart.py            # 开机自启（注册表）
│   └── utils.py                # 资源路径工具
├── ui/
│   ├── main_window.py          # 主窗口 + 系统托盘
│   ├── title_bar.py            # 自定义标题栏（拖拽）
│   ├── split_view.py           # 双栏视图（文本/图片）
│   ├── clip_list.py            # 卡片列表控件
│   ├── clip_card.py            # 单条记录卡片
│   └── tag_dialog.py           # 标签管理 + 选择对话框
└── resources/
    ├── generate_icons.py       # 图标生成脚本
    └── icons/
        ├── app_icon.png        # 256x256 图标
        └── app_icon.ico        # 多尺寸图标
```

## 技术栈

- **Python 3.13** — 主语言
- **PyQt6** — GUI 框架（无边框窗口、系统托盘、自定义控件）
- **SQLite** — 本地数据库（WAL 模式，持久化存储）
- **Pillow** — 图片处理（剪贴板图片抓取、缩略图生成）
- **pywin32** — Windows API（剪贴板操作、注册表读写、原生窗口操作）
- **PyInstaller** — 打包为单 exe

## 数据存储

数据库位置：`C:\Users\<用户名>\.clipmate\clipmate.db`

- 程序关闭后数据持久保留
- 重新打开自动读取已有记录
- `CREATE TABLE IF NOT EXISTS` 确保不会误删数据
- 日志文件：`C:\Users\<用户名>\.clipmate\monitor.log`

### 自动清理

每天首次启动时执行一次清理，然后回收 SQLite 文件空间：

- 图片：超过 **90 天**，或图片总量超过 **300 MB** 时，删除最旧的非收藏/非标签图片
- 文本：超过 **365 天**
- 收藏和已打标签的记录**永久保留**
- 清理后执行 `VACUUM`，文件会真正缩小
- 首次启动可能因清理和 VACUUM 多花 1~2 秒

### 日志

- `monitor.log` 使用轮转：单文件最大 5 MB，保留 3 份，总计不超过约 20 MB
- 剪贴板被其他程序占用时，每分钟最多记录一条警告
- 日志不再记录复制文本的内容，只记录长度

### 如何查看数据库

用 DB Browser for SQLite、Navicat、IntelliJ IDEA / PyCharm 的 Database 工具打开：

```
C:\Users\<用户名>\.clipmate\clipmate.db
```

主要看 `clips` 表：

- `text_content`：完整复制的文本
- `image_data`：原图 PNG BLOB
- `image_thumb`：缩略图
- `preview`：列表里的摘要（前 120 字符）
- `created_at`、`is_favorite`

图片 BLOB 需要工具的预览/导出功能；也可以直接在 ClipMate 里双击查看。建议先退出 ClipMate，或复制一份 `.db` 文件再打开。

### 隐私说明

- 数据库是**明文 SQLite，没有加密**，保存所有未清理的复制文本和图片。
- 能登录你 Windows 账户的人或进程可以直接读取这个文件。
- 不要收藏密码、密钥等敏感内容；收藏会永久保留。
- 旧日志中曾记录文本前 50 个字符，现已删除；新日志不再记录内容。
- 建议开启 BitLocker，不要把 `.clipmate` 目录放进云同步文件夹。
- 如果复制了敏感内容，用托盘“🗑️ 清空”菜单及时清理。

## 运行与开机自启

- 关闭窗口 = 隐藏到托盘，监听线程继续运行；退出用托盘菜单“🚪 退出”。
- 托盘菜单“🚀 开机自启”写入 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`。
- 打包版的自启命令为 `"<安装路径>\ClipMate.exe" --hidden`，登录后隐藏启动。
- 已加单实例锁：重复启动会提示“ClipMate 已在运行”；`--hidden` 启动时静默退出。
- Windows 11 可能把托盘图标收进任务栏的 `^` 溢出区。

## 发布到 GitHub Releases

1. 本地确认程序可以正常运行，并重新打包 `dist/ClipMate.exe`。
2. 提交源码和文档，不要提交 `dist/`、`build/`。
3. GitHub 仓库 → Releases → Draft a new release → 新建 tag（例如 `v1.0.1`）→ 上传 `dist/ClipMate.exe` → Publish。
4. 别人从 Releases 下载单个 exe 即可运行，不需要 Python。
5. exe 未签名，首次运行可能触发 SmartScreen 或杀软拦截，需要“更多信息 → 仍要运行”。

## 已知限制

- 目前只支持 Windows x64，不支持 macOS、Linux、32 位 Windows。
- 输出是便携版 exe，不是安装向导；卸载需删除 exe、`%USERPROFILE%\.clipmate` 和自启注册表项。
- 数据库未加密，敏感内容请及时清理。
- 没有代码签名，没有自动更新，没有崩溃自动重启。
