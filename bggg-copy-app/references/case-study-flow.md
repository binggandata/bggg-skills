# 案例：FlowClone（Google Flow 净室复刻）

## 起点
- 设备：Xiaomi Mi 9 Pro 5G（Android 11/MIUI 13，1080×2340），adb `d0673a58`
- 目标：净室复刻 Google Flow 的移动端功能；可先 Web 原型，最终交付原生 APK
- 生成后端：NGSFlow AI Gateway（图片/视频/文本模型）
- 约束：不反编译、不搬代码素材；原版账号只在允许范围内做 UI 采集

## 方法
1. ADB 接入：截图 + uiautomator + input；自写 `tools/ui.py`/`cap.sh`
2. 分层探索 3–5 层：首页→项目→素材→编辑/延长/动画→高级设置
3. 规格：`spec/ui-spec-v0.md`、`ui-diff-table.md`、行为观察 S1–S58
4. 重建：Kotlin/Compose（约 5.1k 行）+ Python Server（743 行）
5. 对比：16 组并排图（`evidence/compare-best/`）+ 效果级审计
6. 商业化骨架：注册/登录/额度/任务/通知/LLM/发布包

## 结果
- 真实生成跑通（Grok 图/视频）、延长 16s 整段可播放、编辑同素材多版本、多份生成、失败/恢复、通知、计费对齐
- 已知限制：虚拟形象实拍用系统相机；原版私有模型无法复刻；缺支付/FCM/HTTPS/邮件
- 深坑：网关分段分辨率不同导致拼接后段不可解码（Media3 Transformer 修复）；上传 401/202/下载慢；项目归属跳转 bug

## 可复用点
- `bggg-copy-app` 的所有 references/templates 均从该项目提炼
- 开源仓库：FlowClone（见项目 `dist/flowclone-opensource/`）
