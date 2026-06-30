# ClipMate - Windows 剪贴板历史管理工具

个人 Windows 桌面剪贴板管理工具，解决系统只能保留最后一次复制内容的痛点。

## 功能

- 🔍 **历史记录** — 自动监听剪贴板，保存文本和图片历史
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
python main.py
```

### 打包为 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name ClipMate \
  --icon resources/icons/app_icon.ico \
  --add-data "resources/icons/app_icon.png;resources/icons" \
  --add-data "resources/icons/app_icon.ico;resources/icons" \
  main.py
# 输出: dist/ClipMate.exe
```

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
