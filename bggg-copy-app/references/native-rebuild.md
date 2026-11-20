# 重建层：技术栈、架构与异步生成

## 1. 技术栈选择

| 场景 | 推荐 | 说明 |
|---|---|---|
| 真机就是 Android、要最高保真 | **Kotlin + Jetpack Compose** | 控件/手势/播放器/相机原生能力最完整 |
| 快速验证 UI | Web/PWA 原型 | 只用于验证布局/流程，不做最终交付 |
| 跨端预算有限 | Flutter/RN | 注意平台差异与原生能力（视频/相机/文件） |
| 后台服务 | Python stdlib / FastAPI / Node | 小项目 stdlib 足够；正式上云建议 FastAPI/Node + Postgres |

**本项目**：Android 11 真机 → Kotlin 2.0.21 + Compose BOM 2024.09；服务端 Python 3 stdlib（零依赖）+ sqlite3。

## 2. App 架构（可复用）

```
MainActivity (single activity)
 ├─ Screen 状态机：Home / Project / Asset / Set / Notifications / Account
 ├─ ComposerUi + ComposerScreen（Agent/Image/Video 模式）
 ├─ Repo（内存模型 + JSON 持久化：项目/素材/版本/通知）
 ├─ Gateway（生成后端客户端：submit/poll/download/cancel）
 └─ 播放/图片：Media3 ExoPlayer、Coil/自绘
```

关键数据模型：
- `FlowAsset`：type/title/model/quality/prompt/status/progress/localPath/versions/jobId/lastError/extendBasePath
- `versions`：编辑/延长追加，原文件保留；UI 用右侧指示条 + 循环滑动
- `jobId` 持久化：进程被杀后启动时续查

## 3. 生成任务（必须异步化）

```
submit(prompt, params) -> jobId
persist(jobId)
loop: GET /jobs/{id} until succeeded/failed（退避 3s，超时上限）
download outputs -> 本地文件
apply: 新素材 or append 到 versions
notify: 仅按原版规则
```
失败处理：
- 保留 jobId（可恢复）→ 启动/回前台自动续查
- 明确错误文案（点数不足/网络/任务不存在）
- 重试优先续查原任务（避免重复扣费）

## 4. 服务端 BFF（若需要）

- 账号：注册/登录（PBKDF2）、access+refresh、游客、注销级联
- 额度：账本；生成前检查；失败/取消按规则退款
- 任务：本地 job ↔ 上游 job 映射；状态轮询；输出缓存（上游内容慢时先缓存再给客户端）
- 通知：任务完成写表；推送 token 登记
- LLM：`/v1/agent/chat` 代理文本模型（Key 只在服务端）
- 管理：只读 Admin（用户/任务/账单/统计）

## 5. 媒体拼接（视频延长/合并的坑）

- 上游不同次生成可能分辨率/编码参数不同（例如 416×752 vs 400×736），**不能直接用 MediaMuxer 拼**，第二段会无法解码（花屏/黑屏）。
- 方案：**Media3 Transformer**（`media3-transformer` + `media3-effect`）：对每段加 `Presentation.createForWidthAndHeight` 统一尺寸，再 `EditedMediaItemSequence` 拼接、输出重编码 MP4。
- 备选：MediaCodec 手动 decode→scale→encode（复杂）；ffmpeg-kit（依赖大、需评估许可证）。
- 拼接后校验：时长 = 各段之和；连续抽帧检查后半段；播放器无解码错误。

## 6. 其他工程要点
- release/debug 签名不同，切换安装需 `adb uninstall`
- 网关 Key 只在服务端；App 端 `gateway.properties` 留空 key
- 生成/下载超时要大于上游最慢场景（如 10 分钟），并显示"缓存中"进度
- 本地数据按账号隔离（本项目未做，属已知限制）
