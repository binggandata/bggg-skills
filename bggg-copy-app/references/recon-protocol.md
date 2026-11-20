# 设备接入与探索协议（A 层）

## 1. 接入前检查清单

```bash
adb devices                     # 必须出现 device 而非 unauthorized/offline
adb shell getprop ro.build.version.release   # Android 版本
adb shell wm size; adb shell wm density      # 分辨率/密度（决定 dp 换算）
adb shell dumpsys window | grep mCurrentFocus  # 当前前台
```

- 打不开 App：先确认是否安装（`pm list packages | grep 包名`）、是否被商店地区限制。
- 国行/无 GMS：Google 系 App 可能无法登录；不要在账号配置上钻牛角尖，先确认用户允许范围。
- 网络：自建服务用 `adb reverse tcp:8081 tcp:8081`，App 访问 `127.0.0.1:8081`。
- 保持屏幕常亮：`adb shell svc power stayon true`；防止 MIUI 后台限制（必要时 `dumpsys deviceidle`）。

## 2. 单步采集（每步都做）

```bash
# 截图（视觉证据）
adb exec-out screencap -p > evidence/nNNN-<page>-<state>.png
# 语义树（结构证据）
adb shell uiautomator dump /sdcard/u.xml
adb exec-out cat /sdcard/u.xml > /tmp/u.xml
# 解析出可点击元素（用 scripts/ui.py）
python3 scripts/ui.py show /tmp/u.xml
# 记录状态变化（templates/exploration-log.md）
```

### 选择器优先级
1. `text` / `content-desc` 文本（最稳，但可能多语言/动态）
2. 邻近锚点（同容器/上一行标题）
3. 精确 bounds + 重新 dump 校验（兜底，避免坐标漂移）
4. 绝不复用上一次的坐标。

### 点击/输入
```bash
python3 scripts/ui.py tap '搜索'     # 自动找 text/desc
adb shell input tap X Y              # 确认 bounds 后
adb shell input text 'hello%sworld'  # %s = 空格
adb shell input keyevent 4           # 返回/收键盘（注意：再按可能退出页面）
adb shell input swipe X1 Y1 X2 Y2 300
```

## 3. 分层探索协议（3–5 层）

对每个入口，按层记录：

| 层 | 记录内容 |
|---|---|
| L1 入口 | 首页/导航入口名称、位置、跳转目标 |
| L2 列表/主页 | 卡片数量、筛选 chips、空态、底部栏 |
| L3 详情页 | 标题/模型/分辨率、操作按钮、版本/多选、菜单 |
| L4 编辑/弹层 | composer、设置面板、键盘态、成本/比例/数量 |
| L5 高级/边界 | 失败、取消、权限、多版本、连续编辑、回收站 |

**每层都要覆盖状态矩阵**：正常 / 空 / 加载 / 失败 / 选中 / 多版本 / 键盘 / 弹窗。

## 4. 生成类功能的行为观察

- 提交前后：点了什么、出现什么 loading、进度百分比、文案变化
- 完成后：产物是"新素材"还是"同素材新版本"？卡片角标变化？时长/尺寸？
- 通知：是否发通知、标题/文案/时间、是否只对某类任务发
- 计费：扣多少点、余额变化、与 UI 显示是否一致
- 失败/取消：错误文案、卡片状态、重试/恢复路径

## 5. 常见设备干扰与处理

| 干扰 | 表现 | 处理 |
|---|---|---|
| MIUI 小爱/全局搜索 | 误触后出现语音助手/搜索 | 立即 `keyevent 4` 退出；每次点击前校验前台 |
| 键盘遮挡 | 输入框/按钮位置变化 | 先收起键盘再 dump；或直接用坐标前重新 dump |
| 通知栏/悬浮窗 | 顶部遮挡 | `cmd statusbar collapse` 或先上滑收起 |
| 屏幕熄灭 | 操作无效 | `svc power stayon true`；`input keyevent KEYCODE_WAKEUP` |
| 动画未结束 | 截图/dump 是中间态 | 操作后固定等待 1–3s 再采集 |
