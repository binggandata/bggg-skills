# 飞书确认后发布

默认分工：**用户身份创建并拥有报告文档，机器人身份只发送通知。** 不让机器人默认成为报告所有者。

## 发布前确认

必须向用户确认：

1. 本地 `report.md` 的最终版本。
2. 文档标题和父文件夹／知识库位置；未指定时创建到用户个人云空间。
3. 通知对象：群名／`chat_id` 或个人 `open_id`。
4. 通知正文。
5. 发送身份为机器人；目标群必须已添加该机器人。

## 创建与回读

从报告目录运行，路径必须是 cwd 内相对路径：

```bash
lark-cli docs +create --as user --doc-format markdown --title "报告标题" --content @report.md
lark-cli docs +fetch --as user --doc '<returned-url>' --detail simple
```

创建成功后必须回读，核对标题、核心章节、候选数量和报告链接。写入成功响应本身不等于交付验证。

## 机器人通知

先用只读搜索确定唯一目标群；同名或多结果时必须让用户选择：

```bash
lark-cli im +chat-search --as bot --query "目标群名" --page-size 10
```

用户确认群、通知正文和机器人身份后发送：

```bash
lark-cli im +messages-send --as bot --chat-id oc_xxx \
  --markdown $'## 多平台趋势选品报告\n\n报告已生成：[查看飞书报告](DOC_URL)'
```

发送时使用稳定的幂等键。机器人不在群、权限不足或发送失败时，保留已创建文档并报告具体错误；不得自动改用用户身份发送，也不得向其他相似群重试。

## 安全边界

- 不把 Sorftime Key、Cookie、Token、原始个人资料或本地绝对路径写入飞书。
- 不自动创建群、拉人、转移文档所有权或修改权限。
- 未经确认不更新固定知识库节点；默认新建文档。
