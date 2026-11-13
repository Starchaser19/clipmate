# ClipMate 技术路线详解

## 一、整体架构

```
                    ┌──────────────────────────┐
                    │     ClipMate.exe /        │
                    │     python main.py        │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
     ┌────────────┐    ┌──────────────┐     ┌──────────────┐
     │  主进程     │    │  监听线程     │     │  SQLite DB   │
     │  (PyQt6)   │◄───│  (daemon)    │────►│  (持久化)    │
     └────────────┘    └──────────────┘     └──────────────┘
```

**主进程（GUI）**：PyQt6 事件循环驱动，负责窗口渲染、用户交互、托盘菜单。

**监听线程**：`threading.Thread(daemon=True)` 后台运行，0.5 秒间隔轮询剪贴板，检测文本和图片变化，写入数据库。主进程关闭时自动跟随退出。

**SQLite 数据库**：WAL 模式，支持并发读写。存储在用户目录，跨会话持久化。

---

## 二、数据库设计

### 表结构

```sql
-- 剪贴板记录
CREATE TABLE clips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type TEXT NOT NULL DEFAULT 'text',  -- 'text' | 'image'
    text_content TEXT,          -- 文本内容
    image_data  BLOB,          -- 图片 PNG 原始数据
    image_thumb BLOB,          -- 缩略图（200px）
    file_path   TEXT,          -- 文件路径（预留）
    preview     TEXT,           -- 列表摘要（前120字）
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_favorite INTEGER DEFAULT 0
);

-- 标签
CREATE TABLE tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT DEFAULT '#6366F1'
);

-- 记录-标签 多对多
CREATE TABLE clip_tags (
    clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (clip_id, tag_id)
);
```

### 去重策略

- **文本**：与上一条文本记录比较，相同则只更新时间戳，不新增行
- **图片**：计算 PNG 数据的 MD5 哈希，与上次捕获比较，相同则跳过
- **自复制防护**：ClipMate 自身复制到剪贴板后，调用 `mark_text_seen()` / `mark_image_seen()` 更新监听器基线，避免回环

### 数据清理

`app/maintenance.py` 在每天首次启动时执行一次清理：

- 图片超过 90 天，或图片总量超过 300 MB 时，删除最旧的非收藏/非标签图片
- 文本超过 365 天
- `is_favorite=1` 和出现在 `clip_tags` 中的记录永远保留
- 删除后执行 `VACUUM`，SQLite 文件才会真正缩小
- 清理时间记录在 `~/.clipmate/last_cleanup`，24 小时内不重复执行

数据库是明文 SQLite，没有加密。敏感内容需要用户手动清空，或收藏策略需要谨慎使用。

---

## 三、剪贴板监听

### 轮询机制

```python
while not stopped:
    check_clipboard()    # 检查文本 + 图片
    sleep(0.5)           # 0.5 秒间隔
```

### 变更通知

监听线程每写入一条新记录就递增 `change_seq`（`threading.Lock` 保护）。
GUI 的 2 秒定时器只比较这个计数，计数不变时不做任何查询。
计数变化时调用 `refresh_new()`，只追加新卡片，不重建已有列表。

### 文本检测

```python
import pyperclip
current = pyperclip.paste()
if current != last_text:
    add_to_db(current)
    last_text = current
```

### 图片检测（Pillow ImageGrab）

```python
from PIL import ImageGrab
img = ImageGrab.grabclipboard()   # 一行搞定，支持所有 Windows 格式
if img:
    # 生成缩略图 → PNG 编码 → 写入 DB
    thumb = img.copy(); thumb.thumbnail((200, 200))
    add_to_db(content_type='image', image_data=png_data, image_thumb=thumb_data)
```

`ImageGrab.grabclipboard()` 内部自动处理 CF_DIB、CF_BITMAP、CF_DIBV5 等所有 Windows 剪贴板图片格式，无需手工拼接 BMP 文件头。

### 线程安全

监听线程是 Python daemon 线程，主进程退出时自动终止。Python GIL 保证了字符串/字节赋值的原子性。`change_seq` 用 `threading.Lock` 保护。SQLite WAL 模式支持一写多读并发。

### 日志

`monitor.log` 使用 `RotatingFileHandler`：单文件 5 MB，保留 3 份，总计不超过约 20 MB。
剪贴板被其他程序占用时，每分钟最多记录一条警告，不再每次写完整 Traceback。
日志只记录新记录的数量/长度/图片尺寸，不记录复制文本的内容。

---

## 四、GUI 架构

### 窗口层级

```
MainWindow (QMainWindow)
│  FramelessWindowHint | WA_TranslucentBackground
│
└── centralWidget (outer, margin=12px → 阴影空间)
    │  QGraphicsDropShadowEffect (模糊20px, 偏移3px)
    │
    └── mainContainer (border-radius: 10px, bg: white)
        ├── TitleBar (48px, 可拖拽, 最小化+关闭)
        ├── Toolbar (40px, 标签管理+清空)
        ├── SplitClipView (搜索栏 + 左右双栏)
        │   ├── ClipListWidget (text)    65% 宽度
        │   └── ClipListWidget (image)   35% 宽度
        └── StatusBar (28px)
```

### 自定义标题栏（无边框窗口）

1. **去原生标题栏**：`setWindowFlags(FramelessWindowHint | Window)`
2. **补回功能**：`_fix_window_frame()` 恢复 `WS_THICKFRAME`（边缘缩放）+ `WS_SYSMENU`（任务栏右键菜单）+ `WS_MINIMIZEBOX`（任务栏点击切换）
3. **窗口拖拽**：调用 Windows API `ReleaseCapture() + SendMessage(WM_SYSCOMMAND, SC_MOVE)` → 系统接管拖拽，硬件加速，零延迟
4. **边缘缩放**：`nativeEvent` 拦截 `WM_NCHITTEST`，判断鼠标在边缘 12px 内则返回对应方向码，Windows 自动变为调整大小光标

### 图片单击/双击区分

Qt 双击事件序列：`press → release → press → doubleClick → release`

```python
# mouseReleaseEvent: 启动 250ms 计时器
# mouseDoubleClickEvent: 停止计时器 + 设 _skip_release=True → 跳过下一次 release
# 250ms 计时器到期 → 确认是单击 → 复制到剪贴板
```

关键：双击后第二次 `mouseReleaseEvent` 会重新启动计时器，需用 `_skip_release` 标记跳过。

### 托盘打开与任务栏图标

托盘打开调用 `show_and_raise()`。它先 `show()`，再用 `QTimer.singleShot(0, ...)` 延后列表更新。
任务栏在窗口显示后会发送 `WM_GETICON` 查询窗口图标。
GUI 线程忙时查询会超时，Windows 回退到窗口类图标 `IDI_APPLICATION`，显示为通用应用图标。
因此 `_after_show()` 在列表更新完成后再设置一次窗口图标。
列表查询改为只读轻量字段后，全量刷新从 2.09 秒降到约 0.4~0.6 秒；增量刷新通常低于 10 毫秒。

### 自复制回环防护

```
用户点卡片 → 复制到剪贴板 → mark_text_seen(text)
                                    ↓
监听器下次轮询 → current == _last_text → 跳过 ✓
```

---

## 五、开机自启原理

### Windows 注册表 Run 键

```
路径：HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
键名：ClipMate
值：  "D:\Python\pythonw.exe" "F:\ClipMate\main.py"    （源码运行）
  或  "F:\ClipMate\dist\ClipMate.exe"                  （打包后）
```

Windows 在用户登录后自动执行 `Run` 键下所有程序。`pythonw.exe` 是无控制台窗口版本，启动不会闪黑框。

### 代码实现 (`app/autostart.py`)

```python
# 检测环境
if getattr(sys, 'frozen', False):
    cmd = sys.executable           # 打包模式：exe 本身
else:
    cmd = f'"{pythonw}" "{main.py}"'  # 源码模式：pythonw + 脚本

# 写入注册表
key = winreg.OpenKey(HKEY_CURRENT_USER, r"Software\...\Run", ...)
winreg.SetValueEx(key, "ClipMate", 0, REG_SZ, cmd)

# 删除（禁用时）
winreg.DeleteValue(key, "ClipMate")
```

### 用户操作

托盘右键 → 勾选 `🚀 开机自启` → 写入注册表 → 立即生效。取消勾选则删除键值。

### 单实例锁

`main.py` 在启动时创建会话级命名互斥体 `Local\ClipMate.SingleInstance`。
如果 `GetLastError()` 返回 `ERROR_ALREADY_EXISTS`，说明已有实例在运行：

- 普通启动：弹出提示“ClipMate 已在运行（系统托盘）”，然后退出
- `--hidden` 启动：静默退出，避免开机自启和手动启动打架

互斥体句柄保存在模块级变量中，进程退出时由系统释放。

---

## 六、打包原理 (PyInstaller)

### 打包命令

```
pyinstaller --noconfirm ClipMate.spec
```

`ClipMate.spec` 已经声明了 `--onefile`、`--windowed`、图标和 `resources/icons` 数据文件。

### 各阶段

```
Phase 1: Analysis
  └── 从 main.py 入口开始，递归分析所有 import 语句
      找到：PyQt6, Pillow, pyperclip, pywin32, sqlite3, ctypes, ...
      收集所有 .py 源码、.dll 动态库、数据文件

Phase 2: PYZ (Python Zip Archive)
  └── 将所有 .pyc 字节码打包为单个压缩文件
      包括标准库 + 第三方库 + 项目代码

Phase 3: PKG (C Archive)
  └── 将 PYZ + Python 解释器 DLL + Qt DLL + 资源文件
      打包为单个二进制归档

Phase 4: EXE
  └── 启动引导器 runw.exe + 图标 + PKG 归档 → 合并为 ClipMate.exe
      runw.exe 是无窗口启动器，双击时：
        1. 自解压 PKG 到 %TEMP%\_MEIxxxxx\
        2. 启动嵌入的 Python 解释器
        3. 执行 main.py
        4. 退出时清理临时目录
```

### 资源文件路径

```python
# app/utils.py
def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS    # 打包模式：临时解压目录
    else:
        base = os.path.dirname(os.path.dirname(__file__))  # 源码模式：项目根
    return os.path.join(base, relative_path)
```

所有图标加载统一通过 `resource_path('resources/icons/app_icon.png')`。

### 产物

| 文件 | 大小 | 说明 |
|------|------|------|
| `dist/ClipMate.exe` | ~55MB | 单文件，直接运行，不需要 Python |
| `ClipMate.spec` | ~2KB | PyInstaller 配置文件，下次 rebuild 可用 |

55MB 中：Qt6 DLL ~40MB，Python 标准库 + .pyc ~8MB，Pillow ~3MB，其他 ~4MB。

---

## 七、数据流向全景

```
用户按 Ctrl+C (或截图)
        │
        ▼
   Windows 剪贴板
        │
        ▼ (0.5s 轮询)
  ClipboardMonitor (后台线程)
   ├── pyperclip.paste()      → 检测文本变化
   └── ImageGrab.grabclipboard() → 检测图片变化
        │
        ├─ 去重检查 (MD5 / 文本比较)
        └─ 自复制检查 (mark_seen)
        │
        ▼
  SQLite DB (clipmate.db)
        │
        ▼
  ClipboardMonitor.change_seq 递增
        │
        ▼
  _auto_refresh 每 2s 比较计数
        │ 有变化
        ▼
  ClipListWidget.refresh_new() 只追加新卡片
        │
        ▼
  用户看到界面更新
        │
        ├─ 单击文本 → pyperclip.copy() → 写回剪贴板
        ├─ 单击图片 → win32clipboard.SetClipboardData() → 写回剪贴板
        └─ 双击图片 → os.startfile(tmp.png) → Windows 照片应用预览
```

---

## 八、关键依赖说明

| 依赖 | 版本 | 用途 |
|------|------|------|
| PyQt6 | ≥6.7 | GUI 框架：窗口、控件、托盘、QTimer、QGraphicsDropShadowEffect |
| Pillow | ≥10.0 | ImageGrab 图片抓取、缩略图、格式转换 |
| pyperclip | ≥1.9 | 跨平台文本剪贴板读写 |
| pywin32 | ≥306 | win32clipboard(DIB 格式操作)、winreg(注册表)、win32con |
