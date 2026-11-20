# 在 DeepSeek Harness 里跑复刻（并行与轮次）

## 1. 推荐执行结构

```
Goal（长目标）
 └─ Round 1..N（每轮一个可验收子目标）
     ├─ scout：探索原版（截图/UI树/状态记录）
     ├─ builder：按规格实现
     ├─ checker：同流程对比 + 效果级验证
     └─ 证据归档 + 差异表更新
```
- **每轮必须产出可验证的东西**（1 个页面/1 个功能/1 份对比表），不要"只调研"。
- 目标描述里写清深度等级（L3/L4）与验收方式。
- 用 `todo_write` 维护本轮清单；长任务用 background job（编译/下载/生成）避免阻塞。

## 2. 工具使用建议
- `bash`：ADB/构建/服务器/网关调用（本项目 1,436 次，主力）
- `read_image`：看截图（136 次）；先把多图拼成 montage 减少调用
- `write/edit`：代码与文档
- `present`：交付 PDF/HTML/对比图
- `skill`：加载方法论（如本 skill、dsh-doc）
- 子代理：可按"探索/实现/验收"拆分，但共享同一工作区，需约定写作用域

## 3. 每轮收尾模板
1. 本轮完成了什么（页面/功能/修复）
2. 证据（截图编号、对比图、日志/DB 数值）
3. 与原版差异（UI/行为）与下一步
4. 更新 `PROGRESS.md`、`spec/ui-diff-table.md`、`spec/behavior-audit.md`

## 4. 与 DSH skill 目录
- 本 skill 安装到 `~/.agents/skills/bggg-copy-app/`（用户级）或 `<project>/.dsh/skills/`
- 会话中直接说"用 bggg-copy-app 复刻 X"即可触发；也可让子代理加载
- `dsh-doc` skill 可查 DSH 插件/skill/preset 机制
