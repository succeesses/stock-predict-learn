# TODO: OpenClaw Skill 化（ClawHub 发布标准版）

后续单开 session 处理，不和当前可运行版联调任务混在一起。

这份 TODO 的目标不是“先做个能跑的雏形”，而是直接定义出一条可执行的 Skill 化路径：

- 本地 OpenClaw 可加载和调用
- 后续可发布到 ClawHub
- 不需要下一次 session 再重新做产品边界判断

## 已锁定的前提

- Skill 只承载 `JusticePlutus` 的“股票分析能力”
- 不把整个仓库、GitHub Actions、CI、artifact 上传逻辑当成 Skill 本体
- 首版 Skill 闭环固定为：
  - 输入股票代码
  - 获取行情与技术面
  - 获取搜索增强信息
  - 调用 LLM 输出结构化分析
  - 返回 Markdown / JSON
  - Telegram 推送作为可选 side effect
- 首版以“本地 OpenClaw 可调用优先”为实施目标，但 TODO 内必须同时满足未来 ClawHub 发布标准
- Telegram 不是首版必须打通的硬依赖；Markdown / JSON 输出才是 Skill 最小验收闭环

## 目标产物

最终要产出一个独立的 Skill 目录，而不是整个工程仓库：

```text
justice-plutus/
  SKILL.md
  scripts/
  references/
  .clawhubignore
```

其中：

- `SKILL.md`：Skill 说明、触发条件、调用方式、frontmatter metadata
- `scripts/`：最小可执行脚本
- `references/`：提示词、输出结构、数据源说明等文本参考资料
- `.clawhubignore`：发布到 ClawHub 时排除不应打包的文件

## Phase 1: 锁定 Skill 边界

动作：

- 明确 Skill 只解决“按需分析股票”的问题
- 明确哪些能力属于 Skill 本体，哪些不属于
- 固定首版输入输出边界

产物：

- 一份边界说明，写入 `SKILL.md` 或 `references/overview.md`

验收标准：

- 明确属于 Skill 的能力：
  - 行情获取
  - 搜索增强
  - LLM 分析
  - Markdown / JSON 输出
  - 可选 Telegram 推送
- 明确不属于 Skill 的能力：
  - GitHub Actions workflow
  - 定时调度
  - artifact 上传
  - 仓库级文档与演示工程壳
- 首版默认输入：
  - 单股票优先
  - 多股票保留扩展位，但不是第一阶段必须打通项

## Phase 2: 设计 Skill 目录结构

动作：

- 设计符合 OpenClaw / ClawHub 标准的 Skill 文件夹
- 约束哪些文件允许进入 Skill bundle

产物：

- Skill 目录结构草案
- `.clawhubignore` 规则草案

验收标准：

- Skill 是一个独立目录
- 目录中必须有 `SKILL.md`
- supporting files 仅使用文本文件
- 不把以下内容打进 Skill：
  - `.git/`
  - `reports/`
  - `logs/`
  - 数据库文件
  - GitHub workflow
  - 非文本产物

## Phase 3: 提取最小可复用执行逻辑

动作：

- 从当前项目抽出最小闭环执行逻辑
- 不复制整套工程壳，只保留 Skill 真正需要的执行路径

产物：

- `scripts/analyze_stock.py` 或等价单入口脚本
- 最小公共模块清单

验收标准：

- 必须能力：
  - 行情获取
  - 搜索增强
  - LLM 分析
  - Markdown / JSON 结果生成
- 可选能力：
  - Telegram 推送
- 不依赖 GitHub Actions 才能运行
- 在本地命令行可以独立执行一次分析

## Phase 4: 设计 OpenClaw 本地可用标准

动作：

- 设计 `SKILL.md`
- 写最小 frontmatter
- 补 `metadata.openclaw`

产物：

- `SKILL.md` 初稿

验收标准：

- `SKILL.md` 使用 Markdown + frontmatter
- 最小 frontmatter 字段必须包括：
  - `name`
  - `description`
  - `version`
  - `metadata.openclaw`
- 最小 `metadata.openclaw` 必须包括：
  - `requires.env`
  - `requires.bins`
  - `primaryEnv`
- frontmatter 保持最小稳定，不把复杂运行逻辑塞进 metadata
- `requires.bins` 至少声明：
  - `python`

## Phase 5: 写入 ClawHub 发布标准

动作：

- 把未来发布到 ClawHub 时必须满足的约束直接写进 Skill TODO
- 避免后面做完本地版后又重构一轮

产物：

- ClawHub 发布检查清单

验收标准：

- skill folder 合法
- `SKILL.md` 或 `skill.md` 必须存在
- slug 使用小写 URL-safe 格式
  - 建议：`justice-plutus`
- version 使用 semver
  - 例如：`0.1.0`
- bundle 仅包含允许的文本文件
- 避免超过 ClawHub bundle 大小限制
- frontmatter 声明的 env / bins 与实际脚本行为一致
- TODO 中保留许可证提醒：
  - 面向 ClawHub 发布时，按平台规则处理
  - 不在 Skill 中写与平台规则冲突的许可证条款

## Phase 6: 固定输入输出与环境变量标准

动作：

- 定义 Skill 的输入方式、输出方式、最小环境变量集合

产物：

- 输入输出约定说明
- 环境变量清单

验收标准：

- 首版输入：
  - 单股票代码
  - 未来保留多股票扩展位
- 首版输出：
  - Markdown
  - JSON
- Telegram 推送标记为可选 side effect，而不是最小闭环硬依赖
- TODO 中明确预留这些环境变量：
  - `OPENAI_API_KEY`
  - `AIHUBMIX_KEY`
  - `OPENAI_BASE_URL`
  - `OPENAI_MODEL`
  - `BOCHA_API_KEYS`
  - `TAVILY_API_KEYS`
  - `SERPAPI_API_KEYS`
  - `TUSHARE_TOKEN`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`

## Phase 7: 发布前验证与演示

动作：

- 设计本地 OpenClaw 加载验证
- 设计 ClawHub 发布前 smoke test
- 准备首版演示命令

产物：

- 本地验证步骤
- 发布前检查清单

验收标准：

- 本地 OpenClaw 能识别 Skill
- 所需环境变量缺失时，Skill 会给出可理解的失败提示
- `SKILL.md` frontmatter 能通过基本合规检查
- ClawHub 发布前已完成：
  - bundle 检查
  - 文件类型检查
  - slug / version 检查
  - metadata / 实际依赖一致性检查
- 首版 smoke test 至少包括：
  - 单股票分析
  - Markdown 输出
  - JSON 输出
  - 可选 Telegram 推送验证

## 首版推荐 frontmatter 标准

后续实现时，至少应满足这一层标准：

- `name`
- `description`
- `version`
- `metadata.openclaw`

其中 `metadata.openclaw` 至少要包含：

- `requires.env`
- `requires.bins`
- `primaryEnv`

## 首版默认实现策略

- 优先先做“本地 OpenClaw 可调用”
- 同时从第一天起满足“未来可发布到 ClawHub”的目录和 metadata 约束
- 不把 Telegram 推送作为首版 blocking 条件
- 不把多股票作为第一阶段 blocking 条件
- 不把 GitHub Actions / 定时任务迁入 Skill

## 完成定义

下个 session 开工时，做到以下几点即可视为 TODO 被正确执行：

- 产出独立 Skill 目录
- 产出合规的 `SKILL.md`
- 抽出最小脚本集
- 能本地用 OpenClaw 调起一次分析
- 为未来 ClawHub 发布保留合法的 slug、version、bundle、metadata 结构
