# 交付 / 开源清单

## 1. 交付目录（建议）
```
project/
├─ app/ 或 native/          # 客户端源码（可构建）
├─ server/                  # 自建后端（可运行，含 .env.example）
├─ docs/                    # 架构/复盘/部署/对比报告
├─ spec/                    # UI 规格/差异表/行为审计
├─ tools/                   # 采集脚本（ui.py/cap.sh）
├─ skills/                  # 复刻方法论 skill（可选）
├─ README.md                # 一页跑通
├─ LICENSE
└─ SECURITY.md
```

## 2. 开源前脱敏（必须）
- 删除：网关 Key/`.bak`、API token、keystore、数据库（用户数据）、`outputs/`、构建产物、`local.properties`
- 替换：真实邮箱/密码/Admin token/网关 IP → `<...>`
- 复查：`grep -rE 'pass|token|secret|key|@gmail|@example|12[0-9]\\.'`（人工确认）
- 证据：原版 App 截图/素材可能涉及第三方版权 → 开源仓库默认**不包含**，只保留复刻自有截图或说明
- 第三方代码：注明来源/许可证；不要把别人的 skill/脚本打包进自己的 MIT 仓库

## 3. 可复现性
- 一条命令构建客户端（脚本），一条命令启动服务端（`.env.example`）
- 版本固定（Gradle/JDK/AGP/Compose/Python）
- 快速验证路径：注册/游客 → 生成 1 张图 → 查看历史/通知 → 退出登录

## 4. 文档最低集
- README：它是什么、能做什么、架构图、快速开始、配置、已知限制
- DEPLOY：环境变量、端口、反向代理/HTTPS、systemd/Docker、备份
- SECURITY：密钥管理、上报方式、已知风险
- 对比报告：原版 vs 复刻（UI + 效果），证据索引
- 复盘：过程、决策、踩坑（便于他人学习）
