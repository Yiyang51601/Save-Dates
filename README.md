# Save Dates

从 Outlook 邮件里抽出日程、待办和广告邮件，审过后再写入日历、任务或垃圾箱。默认监听新邮件；写入日历用本机时区，「下周五」按该邮件的收到时间推算。

## 功能

- **日程**：讲座、截止日期、模糊时间（下周、周四左右）→ Outlook 日历
- **待办**：没写时间的作业、待约见面、等回复 → Outlook 任务
- **广告**：带退订/优惠券的推销邮件 → 移到垃圾箱（可撤回）
- **多邮箱**：经典 Outlook 里挂了几个收件箱就一起读，卡片上会标邮箱
- **撤回**：点错后可撤回，或按 `Ctrl+Z`
- **反复提醒**（可选）：日程卡片上勾选后才会多次提醒

已有会议邀请的邮件会跳过，避免和 Outlook 日历重复。

## 运行环境

日常路径：打开并保持运行**经典 Outlook**（`outlook.exe`）。

- 也可以日常用新 Outlook，同时让经典 Outlook 在后台开着
- **新 Outlook**（`olk.exe`）为可选：开发者登记公共客户端后把 ID 写入 `DEFAULT_GRAPH_CLIENT_ID`，再点「登录 Microsoft」
- `run.bat` 需要 Python 3.10+；打包好的 `SaveDates.exe` 不需要 Python

第一次扫描时，若 Outlook 弹出访问提示，选择允许即可。

## 怎么用

启动入口是桌面 / 开始菜单里的 **Save Dates**，或 `dist\SaveDates\SaveDates.exe`（旁边必须保留 `_internal`）。不要运行 `build\` 里的文件。

也可双击 `install_shortcuts.bat`，把带图标的快捷方式装到桌面和开始菜单。

### 打包版（Windows）

1. 从 [Releases](https://github.com/Yiyang51601/Save-Dates/releases) 下载 `SaveDates-windows.zip`
2. 解压后运行 **`SaveDates` 文件夹里的** `SaveDates.exe`
3. 关掉窗口即退出。开机启动默认关，可在设置或托盘菜单里勾选「开机时启动」

### 从源码运行

1. 双击 `run.bat`
2. 右上角显示已连接后，新邮件会出现在待确认列表
3. **示例**：先看界面，不连真实邮箱
4. **补扫**：处理旧邮件
5. 每张卡片可改标题/时间，再选择加入 / 记下 / 清掉、跳过或撤回

自行打包：双击 `build_app.bat`，完成后运行 `dist\SaveDates\SaveDates.exe`。

日志和数据库在本目录 `data/`。浏览器调试：`python -m save_dates --web`

## 识别例子

- `2026年8月20日下午3点`
- `8月25日`、`下周五下午2点`、`周四左右`
- `August 20, 2026 at 3:00 PM`
- `请把第三章看完，另外准备考试`
- `我们约个时间见面`
- 带 `unsubscribe` / `退订` / 优惠券的推销邮件
