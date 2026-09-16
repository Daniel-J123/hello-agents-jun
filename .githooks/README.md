# .githooks — 本地 push 前自动审查

启用方式(每个新 clone 需执行一次):

```bash
git config core.hooksPath .githooks
```

启用后,每次 `git push` 会自动执行:

1. **ruff 静态检查**(未安装会尝试自动 `pip install ruff`)
2. **AI 审查**本次 diff(复用 `.github/scripts/ai_review.py`,与 CI 同款)
   - 密钥读取顺序:已导出的环境变量 → 仓库根 `.env` → `code/chapter6/AutoGenDemo/.env`(支持 `${VAR}` 引用式写法)
   - 发现【必须修复】级问题 → **中止 push**
   - AI 调用失败(网络/配额) → 中止 push(可临时跳过)

跳过方式:

```bash
git push --no-verify              # 跳过整个钩子
AI_REVIEW_ON_PUSH=0 git push      # 只跳过 AI 审查,保留 ruff
```
