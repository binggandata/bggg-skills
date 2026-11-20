---
name: bggg-copy-app
description: 用于对 Android App 做“净室/高保真复刻（clean-room clone）”的端到端工作流：ADB 接管真机 → uiautomator 语义树+截图解析 → 规格化（页面/Token/状态矩阵）→ 原生或跨端重建 → 同流程逐状态对比与效果级验收（时长/归属/计费/通知/失败恢复）→ 证据沉淀与开源交付。当用户说“复刻/克隆这个手机 App”“照着原版做一个”“对比原版和复刻版哪里不一样”“把复刻做到能发布”时使用；不用于绕过授权、反编译第三方闭源 App 或搬运其代码/素材。
---

# bggg-copy-app：Android App 高保真复刻方法论

> 这是“怎么做”的 skill，不是“替你做”的脚本。核心资产是：**接入协议、解析方法、深度标准、效果级验收、踩坑清单、交付规范**。
> 默认工作模式：**净室（只看可见界面与行为，不反编译、不搬代码/素材）**。

## 何时使用 / 何时不要用

**用**：
- 要在真机/模拟器上复刻一个 Android App 的 UI、交互、功能效果
- 要判断“复刻到什么程度才算象”“哪些差异必须修”
- 要搭建可复用的“原版 vs 复刻”对比验收流程
- 要把复刻项目整理成可开源/可交付的仓库

**不用 / 先停**：
- 目标 App 不是自己的、也没有明确授权，而用户要求反编译、抓包破鉴权、绕过风控或搬运素材 → 只做净室可见部分，并说明边界
- 要求破解会员/支付/账号体系 → 拒绝并给合规替代方案
- 要求“一键生成一个完整商用 App” → 先对齐范围与深度等级（见 `references/depth-levels.md`）

## 快速开始（5 步）

1. **确认边界**：目标 App/版本、设备、账号、允许采集范围；默认净室。
2. **接入设备**：`adb devices` → 截图 → `uiautomator dump` → 建立“可点击元素”基线；跑 `scripts/adb-check.sh`。
3. **探索并记录**：按 `references/recon-protocol.md` 做 3–5 层遍历；每次操作前后各留一次 dump + 截图；按 `templates/exploration-log.md` 记状态变化。
4. **规格化**：用 `templates/ui-diff-table.md` 建逐屏差异表；确定 Token、导航图、状态矩阵；对核心功能写 `templates/behavior-audit.md`（效果级）。
5. **重建 + 对比**：按 `references/native-rebuild.md` 选栈实现；用同流程截图对比 + 效果级测试验收；用 `templates/acceptance-report.md` 出报告。

## 核心工作流（五层闭环）

```
0 边界/合规 → 1 接入(ADB) → 2 探索(UI树+截图+状态) → 3 规格(页面/Token/行为)
                                                   ↓
                        5 对比验收 ← 4 重建(App + 服务端 + 生成后端)
```
- **2 探索层**：语义树优先、截图补充；`uiautomator` 拿结构，截图拿颜色/间距/圆角；详见 `references/app-parsing.md`。
- **3 规格层**：UI 差异表 + 行为效果表 + 深度等级；**UI 像不等于功能对**。
- **4 重建层**：原生 Kotlin/Compose 优先（自用），跨端需在 skill 允许范围内选择；服务端/网关异步任务模型见 `references/native-rebuild.md`。
- **5 对比层**：同一操作序列逐步对比 + 效果级验收（时长/版本归属/计费/通知/失败恢复），见 `references/behavior-audit.md`。

## 深度等级（验收必须声明级别）

| 级别 | 名称 | 通过标准（摘要） |
|---|---|---|
| L0 | 截图拼装 | 仅静态假数据，不宣称可复刻 |
| L1 | 界面还原 | 主要页面布局/Token 一致，可导航 |
| L2 | 交互可用 | 点击/输入/返回/弹层/多选等可用 |
| L3 | 效果一致 | 真数据/真生成；产物归属、时长、计费、通知规则与原版一致 |
| L4 | 状态与边界 | 失败/取消/恢复/多版本/权限/并发等边界一致 |
| L5 | 商业化就绪 | 账号/额度/风控/合规/发布/支付/推送/可运维 |

完整定义、证据要求与评分见 `references/depth-levels.md`。**默认交付目标 L3；L4/L5 需明确列出覆盖与未覆盖项。**

## 硬性规则

1. **净室优先**：不反编译、不抓包破鉴权、不复制原版代码/素材/品牌；只观察公开可见 UI 与行为。
2. **证据可追溯**：统一编号 `nNNN-页面-状态.png`；每个结论至少一张截图或一份 dump。
3. **每步重新 dump**：不缓存坐标；点击前确认 `mCurrentFocus`；键盘/弹窗/系统助手都会让旧坐标失效。
4. **效果级优先于像素级**：时长、归属、计费、通知、失败恢复先对齐，再打磨间距字号。
5. **长任务必须可恢复**：生成类功能一律 submit→jobId→poll→download，并落盘 jobId。
6. **密钥不落端**：API Key 只放服务端；App 用自有 token + refresh。
7. **先声明局限**：做不到的部分（如原版私有模型、风控、iOS 侧）明确写“已知限制”，不假装完成。

## 资源索引

| 任务 | 文件 |
|---|---|
| 设备接入与探索协议 | `references/recon-protocol.md` |
| UI 树/截图解析、语义选择器 | `references/app-parsing.md` |
| 深度等级与评分 | `references/depth-levels.md` |
| 效果级对比（行为验收） | `references/behavior-audit.md` |
| 原生重建与技术栈/异步生成 | `references/native-rebuild.md` |
| 踩坑清单（20+ 条） | `references/pitfalls.md` |
| DSH 并行执行与 goal 轮次 | `references/dsh-workflow.md` |
| 交付/开源脱敏清单 | `references/delivery-checklist.md` |
| FlowClone 实战案例 | `references/case-study-flow.md` |
| 模板 | `templates/{project-plan,exploration-log,ui-diff-table,behavior-audit,acceptance-report}.md` |
| 脚本 | `scripts/{adb-check.sh,ui.py,cap.sh}` |

## 一页速查：从 0 到可验收

```bash
# 1) 设备
adb devices && adb shell wm size && adb shell wm density
# 2) 采集一步
adb exec-out screencap -p > evidence/n001-home.png
adb shell uiautomator dump /sdcard/u.xml && adb exec-out cat /sdcard/u.xml > /tmp/u.xml
python3 scripts/ui.py show /tmp/u.xml        # 列出可点击元素
python3 scripts/ui.py tap '搜索'             # 按文本点
# 3) 记录状态变化（见 templates/exploration-log.md）
# 4) 规格化（ui-diff-table + behavior-audit）
# 5) 重建/验收（native-rebuild + acceptance-report）
```

## 停止并询问用户的条件

- 目标 App 的账号/授权状态不明确，或需要绕过风控/支付/会员
- 需要的采集涉及隐私数据、他人内容或违反平台条款
- 深度预期与预算冲突（例如“一周做到 L5 商业化”）→ 先给分级交付方案
- 外部生成后端不稳定/受限，无法验证真实效果 → 改为 L2/L3 局部交付并说明
