# Save Dates

从 Outlook 邮件里抽出日期和待办，**只有你点确认才会写入**。广告可以清到垃圾箱。数据只存在这台电脑上。

默认实时监听新邮件。写入日历时用这台电脑的本地时区；「下周五」按**那封邮件的收到时间**计算。

## 能做什么

- **日程**：讲座、截止日期、模糊时间（下周、周四左右）→ 确认后写入 Outlook 日历
- **待办**：没写时间的作业、待约见面、等回复 → 确认后记成 Outlook 任务
- **广告**：带退订/优惠券的推销邮件 → 确认后移到垃圾箱（可撤回）
- **多邮箱**：经典 Outlook 里挂了几个收件箱就一起读，卡片上会标是哪个邮箱
- **撤回**：点错 ✓ / × 后可撤回，或按 `Ctrl+Z`

已有会议邀请的邮件会自动跳过，避免和 Outlook 日历重复。

## 你需要准备什么

- Windows 上的 **Outlook**，已登录邮箱。两种都可以：
  - **经典 Outlook**（`outlook.exe`）：打开并保持运行即可
  - **新 Outlook**（`olk.exe`）：在 Save Dates 里登录 Microsoft 账号（没有经典 COM 接口，走 Microsoft Graph）
- 也可以两个都装：日常用新 Outlook，让经典 Outlook 在后台开着
- 若用 `run.bat`，需要 Python 3.10+；若用打包好的 `SaveDates.exe`，不需要再装 Python

第一次扫描时，Outlook 可能会弹出“有程序正在访问邮箱”，请选择允许。

新 Outlook / Graph：在 Entra 登记一个**公共客户端**，重定向 `http://localhost`，权限勾选 `Mail.Read`、`Mail.ReadWrite`、`Calendars.ReadWrite`。把应用程序（客户端）ID 填进设置后再登录。

## 怎么用

### 打包好的 Windows 应用（给朋友）

1. 从 [Releases](https://github.com/Yiyang51601/Save-Dates/releases) 下载 `SaveDates-windows.zip`
2. 解压后双击 `SaveDates.exe`
3. 关掉窗口不会退出：程序进入托盘继续监听。右键托盘图标选 **退出** 才真正关掉

### 从源码运行

1. 双击 `run.bat`（会创建虚拟环境并打开独立窗口）
2. 右上角显示已连接后，新邮件会自动出现在待确认列表
3. 点 **示例** 可先看界面，不连真实邮箱
4. 处理旧邮件点 **补扫**
5. 每张卡片可改标题/时间，再：
   - **加入 / 记下 / 清掉**
   - **跳过**
   - **撤回**（若点错了）

若要自己打包：双击 `build_app.bat`，完成后运行 `dist\SaveDates\SaveDates.exe`。

日志和数据库在本文件夹的 `data/`，不会上传到任何服务器。

浏览器调试：`python -m save_dates --web`

## 识别例子

- `2026年8月20日下午3点`
- `8月25日`、`下周五下午2点`、`周四左右`
- `August 20, 2026 at 3:00 PM`
- `请把第三章看完，另外准备考试`
- `我们约个时间见面`
- 带 `unsubscribe` / `退订` / 优惠券的推销邮件
