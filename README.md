# GitHub Repo Report Bot

自动抓取并分析 GitHub 仓库的 Issue、Pull Request 和 Discussion，使用 AI 进行质量评分和智能分析。

## ✨ 功能特性

- 🔍 **自动抓取**：支持抓取 Issue、PR 和 Discussion
- 🤖 **AI 分析**：使用 Qwen AI 对 PR 进行多维度评分和详细分析
- 📊 **智能评分**：6 个维度的专业评分系统（代码质量、测试覆盖率、文档、安全、影响范围、PR价值）
- 📝 **自动报告**：生成 Markdown 报告和 GitHub Issue
- ⏰ **灵活时间维度**：支持今日、昨日、上周三种时间模式
- 🎯 **WIP 支持**：智能识别进行中的 PR，基于预期价值评分

## 🚀 快速入门

### 1. Fork 项目

点击仓库右上角的 `Fork` 按钮，将项目 Fork 到你的 GitHub 账户。

### 2. 配置 GitHub Secrets

> **配置优先级**：GitHub Secrets > `config.yaml` > 默认值
> - 如果配置了 Secrets，优先使用 Secrets 的值
> - 如果 Secrets 未配置，会从 `config.yaml` 读取默认值
> - 如果都没有，使用代码中的默认值

在 Fork 后的仓库中，进入 **Settings → Secrets and variables → Actions**，添加以下 Secrets：

**必需配置**：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `GH_SOURCE_OWNER` | 源仓库所有者（要分析的仓库） | `apache` |
| `GH_SOURCE_REPO` | 源仓库名称 | `incubator-seata` |
| `GH_TARGET_OWNER` | 目标仓库所有者（创建 Issue 的仓库） | `your-username` |
| `GH_TARGET_REPO` | 目标仓库名称 | `your-repo` |
| `GH_TOKEN` | GitHub Token | `ghp_xxxxx` |
| `QWEN_API_KEY` | Qwen API Key | `sk-xxxxx` |

**可选配置**（有默认值）：

| Secret 名称 | 说明 | 默认值 |
|------------|------|--------|
| `GH_SOURCE_TOKEN` | 源仓库专用 Token（可选，默认使用 `GH_TOKEN`） | `GH_TOKEN` |
| `GH_TARGET_TOKEN` | 目标仓库专用 Token（可选，默认使用 `GH_TOKEN`） | `GH_TOKEN` |
| `QWEN_BASE_URL` | Qwen API 基础 URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `QWEN_MODEL` | Qwen 模型名称 | `qwen-plus` |
| `QWEN_MAX_REQUESTS` | 每分钟最大请求数 | `30` |
| `ANALYSIS_PERIOD` | 默认时间维度（today/day/week） | 自动判断（周一 week，其他 day） |
| `ANALYSIS_MAX_PR_COUNT` | 最大 PR 数量 | `200` |
| `ANALYSIS_MAX_ISSUE_COUNT` | 最大 Issue 数量 | `300` |
| `ANALYSIS_MAX_DISCUSSION_COUNT` | 最大 Discussion 数量 | `100` |
| `OUTPUT_REPORT_DIR` | 报告目录 | `reports` |
| `OUTPUT_CREATE_ISSUE` | 是否创建 Issue | `true` |
| `OUTPUT_ISSUE_LABELS` | Issue 标签（逗号分隔） | `automated,report` |

> **关于 Issue 标签**：
> - 标签可以通过 `OUTPUT_ISSUE_LABELS` Secret 配置（例如：`automated,report,daily`）
> - 如果标签不存在，GitHub 会尝试自动创建（需要仓库写权限）
> - 建议在目标仓库中预先创建所需标签，或确保 GitHub Token 有足够的权限
> - 工作流会自动添加时间维度标签（`today`/`daily`/`weekly`）

### 3. 启用 GitHub Actions

1. 进入仓库 **Settings → Actions → General**
2. 在 "Workflow permissions" 部分，选择 **Read and write permissions**
3. 勾选 **Allow GitHub Actions to create and approve pull requests**
4. 点击 **Save** 保存设置

### 4. 运行工作流

工作流会在以下情况自动运行：
- **每天北京时间 00:00**（UTC 16:00）：自动判断模式
  - 如果是周一：运行 `week` 模式（分析上周的数据）
  - 其他日期：运行 `day` 模式（分析昨天的数据）

你也可以手动触发：
1. 进入 **Actions** 标签页
2. 选择 **Daily/Weekly GitHub Repo Analysis** 工作流
3. 点击 **Run workflow**
4. 选择时间维度（`today`/`day`/`week`）
5. 点击 **Run workflow** 按钮

### ⚠️ 重要注意事项

1. **GitHub Token 权限要求**：
   - `GH_TOKEN` 需要以下权限：
     - ✅ `repo`（完整仓库访问权限）
     - ✅ `issues:write`（创建和编辑 Issue）
     - ✅ `pull_requests:read`（读取 PR 信息）
   - 如果源仓库和目标仓库不同，确保 Token 对两个仓库都有相应权限
   - 创建 Token：GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **仓库权限**：
   - 确保 `GH_TOKEN` 对源仓库有**读取权限**（至少是 public 仓库或已授权）
   - 确保 `GH_TOKEN` 对目标仓库有**写入权限**（可以创建 Issue）
   - **Issue 标签权限**：
     - 只有在目标仓库有**写入权限**时才能创建和应用标签
     - 如果标签不存在，GitHub 会尝试自动创建（需要写权限）
     - 建议在目标仓库中预先创建所需标签，避免权限问题
     - 工作流已配置 `issues: write` 权限，但需要确保仓库设置允许 GitHub Actions 写入

3. **Qwen API Key**：
   - 需要有效的 Qwen API Key
   - 确保账户有足够的 API 调用额度

4. **工作流权限**：
   - 必须在仓库设置中启用 GitHub Actions
   - 工作流需要写入权限以提交报告文件

5. **首次运行**：
   - 首次运行可能需要几分钟时间
   - 如果失败，请检查 Actions 日志查看详细错误信息

## 📐 架构与流程

### 核心模块

```
src/
├── main.py              # 主入口，协调整个流程
├── github_client.py     # GitHub API 客户端（REST + GraphQL）
├── qwen_client.py       # Qwen AI 客户端，PR 分析
├── analyzer.py          # 数据分析与处理
└── report_generator.py  # 报告生成器
```

### 工作流程

```
1. 配置加载
   └─> 优先从 GitHub Secrets 读取，其次从 config.yaml 读取，最后使用默认值

2. 数据抓取
   ├─> GitHub REST API：获取 Issue、PR 列表
   ├─> GitHub REST API：获取 PR 详情（文件变更、提交等）
   └─> GitHub GraphQL API：获取 Discussion

3. 时间过滤
   └─> 根据 period 配置过滤时间范围内的数据

4. AI 分析
   ├─> 构建 PR 上下文（代码变更、文件列表、描述等）
   ├─> 调用 Qwen API 进行多维度评分
   └─> 生成详细的分析建议

5. 数据处理
   ├─> 分析 Issue（分类、摘要生成）
   ├─> 分析 PR（评分、类型识别、优先级）
   └─> 分析 Discussion（摘要生成）

6. 报告生成
   ├─> 生成 Markdown 报告（保存到 reports/）
   └─> 创建 GitHub Issue（可选）
```

### 评分维度

| 维度 | 说明 | 权重 |
|------|------|------|
| 代码质量 | 代码风格、可读性、设计模式、最佳实践 | 15% |
| 测试覆盖率 | 单元测试、集成测试、边界情况覆盖 | 15% |
| 文档与可维护性 | 代码注释、文档更新、可维护性 | 15% |
| 合规与安全 | 安全漏洞、合规性、依赖安全 | 15% |
| 影响范围合理性 | 影响范围与重要程度的匹配度 | 15% |
| PR价值与作用 | 业务价值、功能重要性、问题解决程度 | 15% |

**评分等级**：
- `>80`：优秀
- `60-80`：良好
- `<60`：一般

## ⏰ 时间维度

### today（今日播报）
- 分析今天的数据
- 只能手动触发
- 适合实时查看当天活动

### day（每日播报）
- 分析昨天一整天的数据
- 每天自动运行（北京时间 00:00，UTC 16:00），周一除外
- 也可以手动触发
- 适合日常监控

### week（每周播报）
- 分析上周一至上周日的数据（完整一周）
- 每周一自动运行（北京时间 00:00，UTC 16:00）
- 也可以手动触发
- 适合周报总结

## 🔧 GitHub Actions 集成

工作流配置文件：`.github/workflows/daily-analysis.yml`

**运行模式**：
- **自动运行**：
  - 每天北京时间 00:00（UTC 16:00）自动触发
    - 周一：运行 `week` 模式（分析上周的数据）
    - 其他日期：运行 `day` 模式（分析昨天的数据）
- **手动触发**：支持选择 `today`/`day`/`week` 模式

> **提示**：所有配置都从 GitHub Secrets 读取，无需修改代码或配置文件，项目完全通用化。详细配置步骤请参考上方的"快速入门"部分。

## 📊 输出示例

### Markdown 报告

报告保存在 `reports/` 目录，包含：
- PR 评分概要和详细分析
- Issue 分类和摘要
- Discussion 列表和摘要

### GitHub Issue

如果启用 `create_issue: true`，会在目标仓库自动创建 Issue，包含：
- PR 评分概览表格
- 重点 PR 详细分析（前 5 个）
- Issue 分类列表（Bug 报告、功能请求）
- Discussion 列表
- 评分标准说明

**Issue 模板示例**：

```markdown
## 每日分析报告 - `apache/incubator-seata`

**时间范围**: 2025-12-01 00:00:00 UTC 至 2025-12-02 00:00:00 UTC
**生成时间**: 2025-12-02 01:00:00 UTC

### 📊 数据概览

- **Issue 数量**: 15
- **PR 数量**: 8

## 一、Pull Request 分析

### 🔍 PR 评分概览

| PR | 标题 | 作者 | 类型 | 规模 | 总分 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| PR-7827 | test: fix non-deterministic in TableMeta | XiaoyangCai360 | fix | small | 89.5 | closed |
| PR-7826 | feature:Support HTTP/2 response handling | YvCeung | feat | large | 87.5 | open |

### 💡 重点 PR 详细分析

#### PR-7827: test: fix non-deterministic in TableMeta

| 基本信息 | 关键指标 | 综合评分 |
| --- | --- | --- |
| 作者: XiaoyangCai360<br>类型: `fix`<br>优先级: `P3`<br>规模: `small`<br>状态: closed ✅ (已合并) | 变更文件: 2<br>新增: `+15`<br>删除: `-8`<br>提交: 1 | **89.5**<br>(优秀) |

**维度评分** (0-10分)

| 维度 | 评分 |
| --- | --- |
| 代码质量 | **9.0** |
| 测试覆盖率 | **8.5** |
| 文档与可维护性 | **9.0** |
| 合规与安全 | **9.0** |
| 影响范围合理性 | **9.0** |
| PR价值与作用 | **8.5** |

**🤖 AI 分析建议**

> 这是一个高质量的修复 PR，代码质量优秀，测试覆盖充分...

---

## 二、Issue 分析

### 📊 Issue 统计

- **打开**: 8 | **已关闭**: 7
- **Bug 报告**: 5 | **功能请求**: 3 | **其他**: 7

### 🐛 Bug 报告

**Issue-1234**: 修复内存泄漏问题
- 作者: user1 | 状态: open | 评论数: 5
- 摘要: 在长时间运行后出现内存泄漏，需要修复...

### ✨ 功能请求

**Issue-1235**: 添加新的 API 端点
- 作者: user2 | 状态: open | 评论数: 3
- 摘要: 希望添加一个新的 REST API 端点用于...

## 三、Discussion 分析

### 📊 Discussion 统计

- **打开**: 2 | **已关闭**: 1

### 💬 Discussions 列表

**Discussion-100**: 关于性能优化的讨论
- 作者: user3 | 状态: open | 评论数: 10 | 分类: General
- 摘要: 讨论如何优化系统性能...

## 📄 完整报告与评分标准

### 详细报告

查看更详细的报告请访问仓库的 `reports/` 目录。

### 评分标准说明

**综合评分等级**:

| 分数范围 | 等级 | 说明 |
| --- | --- | --- |
| >80 | 优秀 | 代码质量高，测试覆盖充分，文档完善，安全合规，影响范围和价值突出 |
| 60-80 | 良好 | 整体质量较高，有少量改进空间 |
| <60 | 一般 | 基本满足要求，但存在明显改进点 |

**维度评分说明** (0-10分):

- **代码质量**: 代码风格、可读性、设计模式、最佳实践
- **测试覆盖率**: 单元测试、集成测试、边界情况覆盖
- **文档与可维护性**: 代码注释、文档更新、可维护性
- **合规与安全**: 安全漏洞、合规性、依赖安全
- **影响范围合理性**: 根据PR的重要程度和影响范围匹配度评分
- **PR价值与作用**: PR的核心作用、业务价值、功能重要性、是否解决关键问题

---
*此 Issue 由 GitHub Actions 自动创建，分析源仓库: `apache/incubator-seata`*
```

## 🛠️ 开发

### 项目结构

```
.
├── src/                    # 源代码
│   ├── main.py            # 主入口
│   ├── github_client.py   # GitHub API 客户端
│   ├── qwen_client.py     # Qwen AI 客户端
│   ├── analyzer.py        # 数据分析
│   └── report_generator.py # 报告生成
├── reports/                # 生成的报告
├── config.yaml             # 配置文件（GitHub Actions 会从此读取默认值，本地运行可直接修改）
├── requirements.txt        # 依赖列表
└── README.md              # 本文档
```

### 依赖

- `requests`：HTTP 请求
- `pyyaml`：YAML 配置解析
- `python-dateutil`：日期处理
