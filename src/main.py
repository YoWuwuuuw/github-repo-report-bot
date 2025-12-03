import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from .analyzer import analyze_issues, analyze_pull_requests, analyze_discussions, build_pr_context
from .github_client import GitHubClient
from .qwen_client import QwenClient
from .report_generator import generate_markdown_report

# 北京时间时区（UTC+8）
BEIJING_TZ = timezone(timedelta(hours=8))


def load_config(config_path: Path) -> dict:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data or {}


def _resolve_token(token_value: str) -> str:
    """解析 token，支持 ${ENV_VAR} 格式的环境变量引用"""
    if not token_value:
        return os.getenv("GH_TOKEN", "")
    if token_value.startswith("${") and token_value.endswith("}"):
        env_var = token_value[2:-1]
        return os.getenv(env_var, "")
    return token_value


def main() -> None:
    """主入口：读取 GitHub 数据，使用 Qwen AI 分析并生成报告"""
    parser = argparse.ArgumentParser(
        description="GitHub 仓库分析工具：自动分析 Issue/PR/Discussion 并生成报告"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="配置文件路径（默认：config.yaml）",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = (repo_root / args.config).resolve()
    if not config_path.exists():
        raise SystemExit(
            f"配置文件 {config_path} 不存在，请先创建配置文件或设置 GitHub Secrets。"
        )

    cfg = load_config(config_path)
    github_cfg = cfg.get("github", {})
    qwen_cfg = cfg.get("qwen", {})
    analysis_cfg = cfg.get("analysis", {})
    output_cfg = cfg.get("output", {})

    source_cfg = github_cfg.get("source", {})
    source_owner = source_cfg.get("owner")
    source_repo = source_cfg.get("repo")
    if not source_owner or not source_repo:
        raise SystemExit("github.source.owner 和 github.source.repo 必须在配置中指定。")

    source_repo_full_name = f"{source_owner}/{source_repo}"

    target_cfg = github_cfg.get("target", {})
    target_owner = target_cfg.get("owner")
    target_repo = target_cfg.get("repo")
    if not target_owner or not target_repo:
        raise SystemExit("github.target.owner 和 github.target.repo 必须在配置中指定。")

    target_repo_full_name = f"{target_owner}/{target_repo}"

    source_token = _resolve_token(source_cfg.get("token", ""))
    target_token = _resolve_token(target_cfg.get("token", ""))

    source_client = GitHubClient(
        owner=source_owner,
        repo=source_repo,
        token=source_token,
    )

    target_client = GitHubClient(
        owner=target_owner,
        repo=target_repo,
        token=target_token,
    )

    period = analysis_cfg.get("period", "day").lower()
    since_iso = None
    period_label = ""
    period_start = None
    now = datetime.now(timezone.utc)

    if period == "today":
        # 今日模式：从今天北京时间 0 点开始
        now_bj = now.astimezone(BEIJING_TZ)
        today_bj_start = datetime(now_bj.year, now_bj.month, now_bj.day, 0, 0, 0, tzinfo=BEIJING_TZ)
        period_start = today_bj_start.astimezone(timezone.utc)
        period_end = now
        since_iso = period_start.isoformat()
        period_label = "今日"
    elif period == "day":
        period_end = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
        period_start = period_end - timedelta(days=1)
        since_iso = period_start.isoformat()
        period_label = "昨日"
    elif period == "week":
        today = now.date()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        period_start = datetime.combine(last_monday, datetime.min.time(), tzinfo=timezone.utc)
        last_sunday = last_monday + timedelta(days=6)
        period_end = datetime.combine(last_sunday + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        since_iso = period_start.isoformat()
        period_label = "上周（周一至周日）"
    else:
        raise SystemExit(f"不支持的 period 配置: {period}，只支持 'today'、'day' 或 'week'")

    print(f"📊 开始分析 {source_repo_full_name} 的 {period_label} 数据...")
    # 转换为北京时间显示
    period_start_bj = period_start.astimezone(BEIJING_TZ)
    period_end_bj = period_end.astimezone(BEIJING_TZ)
    if period == "today":
        print(f"   时间范围: {period_start_bj.strftime('%Y-%m-%d %H:%M:%S')} 至 {period_end_bj.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    else:
        print(f"   时间范围: {period_start_bj.strftime('%Y-%m-%d %H:%M:%S')} 至 {period_end_bj.strftime('%Y-%m-%d %H:%M:%S')} (北京时间，不包含结束时间)")

    raw_issues = source_client.list_issues(
        state="all",
        since=since_iso,
        max_count=int(analysis_cfg.get("max_issue_count", 300)),
    )

    # 过滤 Issue：区分时间段内创建的 Issue 和有动静的 Issue
    if period_start:
        created_issues = []
        updated_issues = []
        for issue in raw_issues:
            issue_created = issue.get("created_at")
            issue_updated = issue.get("updated_at")
            if issue_created:
                try:
                    created_date = datetime.fromisoformat(issue_created.replace("Z", "+00:00"))
                    updated_date = datetime.fromisoformat(issue_updated.replace("Z", "+00:00")) if issue_updated else created_date

                    # 判断是否在时间段内创建
                    if period == "today":
                        in_period_created = period_start <= created_date <= period_end
                        in_period_updated = period_start <= updated_date <= period_end and updated_date != created_date
                    else:
                        in_period_created = period_start <= created_date < period_end
                        in_period_updated = period_start <= updated_date < period_end and updated_date != created_date

                    if in_period_created:
                        created_issues.append(issue)
                    elif in_period_updated:
                        updated_issues.append(issue)
                except Exception:
                    pass

        # 合并并去重（按 number）
        seen_numbers = set()
        filtered_issues = []
        for issue in created_issues + updated_issues:
            issue_num = issue.get("number")
            if issue_num and issue_num not in seen_numbers:
                filtered_issues.append(issue)
                seen_numbers.add(issue_num)
                # 标记 Issue 是否是在时间段内创建的
                issue["_created_in_period"] = issue in created_issues

        raw_issues = filtered_issues
        print(f"   时间段内创建的 Issue: {len(created_issues)} 个，有动静的 Issue: {len(updated_issues)} 个")

    raw_prs = source_client.list_pull_requests(
        state="all",
        max_count=int(analysis_cfg.get("max_pr_count", 200)),
    )

    if period_start:
        filtered_prs = []
        for pr in raw_prs:
            pr_created = pr.get("created_at")
            if pr_created:
                try:
                    pr_date = datetime.fromisoformat(pr_created.replace("Z", "+00:00"))
                    if period == "today":
                        if period_start <= pr_date <= period_end:
                            filtered_prs.append(pr)
                    else:
                        if period_start <= pr_date < period_end:
                            filtered_prs.append(pr)
                except Exception:
                    pass
        raw_prs = filtered_prs

    raw_discussions = []
    try:
        raw_discussions = source_client.list_discussions(
            since=since_iso,
            max_count=int(analysis_cfg.get("max_discussion_count", 100)),
        )

        # 过滤 Discussion：区分时间段内创建的 Discussion 和有动静的 Discussion
        if period_start and raw_discussions:
            created_discussions = []
            updated_discussions = []
            for disc in raw_discussions:
                disc_created = disc.get("created_at")
                disc_updated = disc.get("updated_at")
                if disc_created:
                    try:
                        created_date = datetime.fromisoformat(disc_created.replace("Z", "+00:00"))
                        updated_date = datetime.fromisoformat(disc_updated.replace("Z", "+00:00")) if disc_updated else created_date

                        # 判断是否在时间段内创建
                        if period == "today":
                            in_period_created = period_start <= created_date <= period_end
                            in_period_updated = period_start <= updated_date <= period_end and updated_date != created_date
                        else:
                            in_period_created = period_start <= created_date < period_end
                            in_period_updated = period_start <= updated_date < period_end and updated_date != created_date

                        if in_period_created:
                            created_discussions.append(disc)
                        elif in_period_updated:
                            updated_discussions.append(disc)
                    except Exception:
                        pass

            # 合并并去重（按 number）
            seen_numbers = set()
            filtered_discussions = []
            for disc in created_discussions + updated_discussions:
                disc_num = disc.get("number")
                if disc_num and disc_num not in seen_numbers:
                    filtered_discussions.append(disc)
                    seen_numbers.add(disc_num)
                    # 标记 Discussion 是否是在时间段内创建的
                    disc["_created_in_period"] = disc in created_discussions

            raw_discussions = filtered_discussions
            print(f"   时间段内创建的 Discussion: {len(created_discussions)} 个，有动静的 Discussion: {len(updated_discussions)} 个")
    except Exception as e:
        print(f"   ⚠️  获取 Discussions 失败（可能未启用）: {e}")

    print(f"   找到 {len(raw_issues)} 个 Issue，{len(raw_prs)} 个 PR，{len(raw_discussions)} 个 Discussion")

    detailed_prs = []
    for pr in raw_prs:
        number = pr.get("number")
        if not number:
            continue
        try:
            detailed = source_client.get_pull_request_detail(number=number)
            detailed_prs.append(detailed)
        except Exception as e:
            print(f"   ?? 获取 PR #{number} 详情失败: {e}")
            continue

    qwen_api_key_raw = qwen_cfg.get("api_key", "")
    if not qwen_api_key_raw:
        qwen_api_key = os.getenv("QWEN_API_KEY", "")
    elif qwen_api_key_raw.startswith("${") and qwen_api_key_raw.endswith("}"):
        env_var = qwen_api_key_raw[2:-1]
        qwen_api_key = os.getenv(env_var, "")
    else:
        qwen_api_key = qwen_api_key_raw

    qwen_client = QwenClient(
        base_url=qwen_cfg.get("base_url", ""),
        api_key=qwen_api_key,
        model=qwen_cfg.get("model", "qwen-plus"),
        max_requests_per_minute=int(
            qwen_cfg.get("max_requests_per_minute", 30)
        ),
    )

    qwen_results: dict[int, dict] = {}
    for pr in detailed_prs:
        ctx = build_pr_context(pr)
        result = qwen_client.analyze_pr(ctx)
        qwen_results[pr.get("number", 0)] = result

    issues_analysis = analyze_issues(raw_issues, qwen_client)
    prs_analysis = analyze_pull_requests(detailed_prs, qwen_results)
    discussions_analysis = analyze_discussions(raw_discussions, qwen_client)

    report_dir = repo_root / output_cfg.get("report_dir", "reports")
    report_path = generate_markdown_report(
        repo_full_name=source_repo_full_name,
        issues=issues_analysis,
        prs=prs_analysis,
        discussions=discussions_analysis,
        report_dir=report_dir,
        period=period,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
    )

    print(f"✅ 报告已生成：{report_path}")

    # 在目标仓库创建 Issue
    create_issue = output_cfg.get("create_issue", False)
    if create_issue and target_token:
        try:
            if period == "today":
                period_display = "今日"
                issue_date = now.strftime('%Y-%m-%d')
            elif period == "day":
                period_display = "每日"
                issue_date = (period_end - timedelta(days=1)).strftime('%Y-%m-%d')
            else:  # week
                period_display = "每周"
                issue_date = f"{period_start.strftime('%Y-%m-%d')} 至 {(period_end - timedelta(days=1)).strftime('%Y-%m-%d')}"
            issue_title = f"{period_display}播报 - {source_owner}/{source_repo} - {issue_date}"

            # 构建 Issue 正文
            # 转换为北京时间显示
            period_start_bj = period_start.astimezone(BEIJING_TZ)
            period_end_bj = period_end.astimezone(BEIJING_TZ)
            now_bj = datetime.now(timezone.utc).astimezone(BEIJING_TZ)

            issue_body_lines = [
                f"## {period_display}分析报告 - `{source_owner}/{source_repo}`",
                "",
                f"**时间范围**: {period_start_bj.strftime('%Y-%m-%d %H:%M:%S')} 至 {period_end_bj.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)",
                f"**生成时间**: {now_bj.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)",
                "",
                "### 📊 数据概览",
                "",
                f"- **Issue 数量**: {len(issues_analysis)}",
                f"- **PR 数量**: {len(prs_analysis)}",
                "",
            ]

            if prs_analysis:
                issue_body_lines.extend([
                    "## 一、Pull Request 分析",
                    "",
                    "### 🔍 PR 评分概览",
                    "",
                    "| PR | 标题 | 作者 | 类型 | 规模 | 总分 | 状态 |",
                    "| --- | --- | --- | --- | --- | --- | --- |",
                ])
                sorted_prs = sorted(prs_analysis, key=lambda x: x.total_score, reverse=True)
                for pr in sorted_prs[:10]:
                    issue_body_lines.append(
                        f"| PR-{pr.number} | "
                        f"{pr.title[:40]} | {pr.author} | {pr.pr_type} | {pr.size_category} | "
                        f"{pr.total_score} | {pr.state} |"
                    )
                issue_body_lines.extend([
                    "",
                    "### 💡 重点 PR 详细分析",
                    "",
                ])

                for pr in sorted_prs[:5]:
                    issue_body_lines.extend([
                        f"#### PR-{pr.number}: {pr.title}",
                        "",
                        "| 基本信息 | 关键指标 | 综合评分 |",
                        "| --- | --- | --- |",
                        f"| 作者: {pr.author}<br>类型: `{pr.pr_type}`<br>优先级: `{pr.priority}`<br>规模: `{pr.size_category}`<br>状态: {pr.state}" + (f" ✅ (已合并)" if pr.merged_at else "") + " | " +
                        f"变更文件: {pr.changed_files}<br>新增: `+{pr.additions}`<br>删除: `-{pr.deletions}`<br>提交: {pr.commits} | " +
                        f"**{pr.total_score}**<br>({pr.rating}) |",
                        "",
                        "**维度评分** (0-10分)",
                        "",
                        f"| 维度 | 评分 |",
                        f"| --- | --- |",
                        f"| 代码质量 | **{pr.code_quality_score}** |",
                        f"| 测试覆盖率 | **{pr.test_coverage_score}** |",
                        f"| 文档与可维护性 | **{pr.doc_maintain_score}** |",
                        f"| 合规与安全 | **{pr.compliance_security_score}** |",
                        f"| 影响范围合理性 | **{pr.merge_history_score}** |",
                        f"| PR价值与作用 | **{pr.collaboration_score}** |",
                        "",
                    ])

                    if pr.qwen_comment and pr.qwen_comment.strip() and pr.qwen_comment != "Qwen API key 未配置，未实际调用模型。" and not pr.qwen_comment.startswith("调用 Qwen 失败"):
                        issue_body_lines.extend([
                            "**🤖 AI 分析建议**",
                            "",
                            "> " + pr.qwen_comment.replace("\n", "\n> "),
                            "",
                        ])

                    issue_body_lines.append("---")
                    issue_body_lines.append("")

            if issues_analysis:
                # 区分时间段内创建的 Issue 和有动静的 Issue
                created_issues = [i for i in issues_analysis if i.created_in_period]
                updated_issues = [i for i in issues_analysis if not i.created_in_period]

                open_issues = [i for i in issues_analysis if i.state == "open"]
                closed_issues = [i for i in issues_analysis if i.state == "closed"]
                bug_reports = [i for i in issues_analysis if i.category == "bug"]
                feature_requests = [i for i in issues_analysis if i.category == "feature request"]
                other_issues = [i for i in issues_analysis if i.category not in ["bug", "feature request"]]

                issue_body_lines.extend([
                    "## 二、Issue 分析",
                    "",
                    "### 📊 Issue 统计",
                    "",
                    f"- **打开**: {len(open_issues)} | **已关闭**: {len(closed_issues)}",
                    f"- **时间段内创建**: {len(created_issues)} | **有动静**: {len(updated_issues)}",
                    f"- **Bug 报告**: {len(bug_reports)} | **功能请求**: {len(feature_requests)} | **其他**: {len(other_issues)}",
                    "",
                ])

                if created_issues:
                    created_bugs = [i for i in bug_reports if i.created_in_period]
                    created_features = [i for i in feature_requests if i.created_in_period]
                    created_others = [i for i in other_issues if i.created_in_period]

                    issue_body_lines.extend([
                        "### 📅 时间段内创建的 Issue",
                        "",
                    ])

                    if created_bugs:
                        issue_body_lines.extend([
                            "#### 🐛 Bug 报告（新创建）",
                            "",
                        ])
                        for issue in sorted(created_bugs, key=lambda x: x.number, reverse=True):
                            issue_body_lines.extend([
                                f"**Issue-{issue.number}**: {issue.title}",
                                f"- 作者: {issue.author} | 状态: {issue.state} | 评论数: {issue.comments}",
                                f"- 摘要: {issue.summary[:150]}",
                                "",
                            ])

                    if created_features:
                        issue_body_lines.extend([
                            "#### ✨ 功能请求（新创建）",
                            "",
                        ])
                        for issue in sorted(created_features, key=lambda x: x.number, reverse=True):
                            issue_body_lines.extend([
                                f"**Issue-{issue.number}**: {issue.title}",
                                f"- 作者: {issue.author} | 状态: {issue.state} | 评论数: {issue.comments}",
                                f"- 摘要: {issue.summary[:150]}",
                                "",
                            ])

                    if created_others:
                        issue_body_lines.extend([
                            "#### 📝 其他 Issue（新创建）",
                            "",
                        ])
                        for issue in sorted(created_others, key=lambda x: x.number, reverse=True):
                            issue_body_lines.extend([
                                f"**Issue-{issue.number}**: {issue.title}",
                                f"- 作者: {issue.author} | 状态: {issue.state} | 评论数: {issue.comments}",
                                f"- 摘要: {issue.summary[:150]}",
                                "",
                            ])

                if updated_issues:
                    updated_bugs = [i for i in bug_reports if not i.created_in_period]
                    updated_features = [i for i in feature_requests if not i.created_in_period]
                    updated_others = [i for i in other_issues if not i.created_in_period]

                    issue_body_lines.extend([
                        "### 🔄 时间段内有动静的 Issue",
                        "",
                    ])

                    if updated_bugs:
                        issue_body_lines.extend([
                            "#### 🐛 Bug 报告（有更新）",
                            "",
                        ])
                        for issue in sorted(updated_bugs, key=lambda x: x.number, reverse=True):
                            issue_body_lines.extend([
                                f"**Issue-{issue.number}**: {issue.title}",
                                f"- 作者: {issue.author} | 状态: {issue.state} | 评论数: {issue.comments}",
                                f"- 摘要: {issue.summary[:150]}",
                                "",
                            ])

                    if updated_features:
                        issue_body_lines.extend([
                            "#### ✨ 功能请求（有更新）",
                            "",
                        ])
                        for issue in sorted(updated_features, key=lambda x: x.number, reverse=True):
                            issue_body_lines.extend([
                                f"**Issue-{issue.number}**: {issue.title}",
                                f"- 作者: {issue.author} | 状态: {issue.state} | 评论数: {issue.comments}",
                                f"- 摘要: {issue.summary[:150]}",
                                "",
                            ])

                    if updated_others:
                        issue_body_lines.extend([
                            "#### 📝 其他 Issue（有更新）",
                            "",
                        ])
                        for issue in sorted(updated_others, key=lambda x: x.number, reverse=True):
                            issue_body_lines.extend([
                                f"**Issue-{issue.number}**: {issue.title}",
                                f"- 作者: {issue.author} | 状态: {issue.state} | 评论数: {issue.comments}",
                                f"- 摘要: {issue.summary[:150]}",
                                "",
                            ])

            if discussions_analysis:
                # 区分时间段内创建的 Discussion 和有动静的 Discussion
                created_discussions = [d for d in discussions_analysis if d.created_in_period]
                updated_discussions = [d for d in discussions_analysis if not d.created_in_period]

                open_discussions = [d for d in discussions_analysis if d.state == "open"]
                closed_discussions = [d for d in discussions_analysis if d.state == "closed"]

                issue_body_lines.extend([
                    "## 三、Discussion 分析",
                    "",
                    "### 📊 Discussion 统计",
                    "",
                    f"- **打开**: {len(open_discussions)} | **已关闭**: {len(closed_discussions)}",
                    f"- **时间段内创建**: {len(created_discussions)} | **有动静**: {len(updated_discussions)}",
                    "",
                ])

                if created_discussions:
                    issue_body_lines.extend([
                        "### 📅 时间段内创建的 Discussion",
                        "",
                    ])
                    for disc in sorted(created_discussions, key=lambda x: x.number, reverse=True):
                        issue_body_lines.extend([
                            f"**Discussion-{disc.number}**: {disc.title}",
                            f"- 作者: {disc.author} | 状态: {disc.state} | 评论数: {disc.comments} | 分类: {disc.category}",
                            f"- 摘要: {disc.summary[:150]}",
                        ])

                        # AI 解释
                        if disc.ai_summary and disc.ai_summary.strip() and not disc.ai_summary.startswith("调用 Qwen 失败"):
                            issue_body_lines.extend([
                                f"- **AI 解释**: {disc.ai_summary}",
                            ])

                        issue_body_lines.append("")

                if updated_discussions:
                    issue_body_lines.extend([
                        "### 🔄 时间段内有动静的 Discussion",
                        "",
                    ])
                    for disc in sorted(updated_discussions, key=lambda x: x.number, reverse=True):
                        issue_body_lines.extend([
                            f"**Discussion-{disc.number}**: {disc.title}",
                            f"- 作者: {disc.author} | 状态: {disc.state} | 评论数: {disc.comments} | 分类: {disc.category}",
                            f"- 摘要: {disc.summary[:150]}",
                        ])

                        # AI 解释
                        if disc.ai_summary and disc.ai_summary.strip() and not disc.ai_summary.startswith("调用 Qwen 失败"):
                            issue_body_lines.extend([
                                f"- **AI 解释**: {disc.ai_summary}",
                            ])

                        issue_body_lines.append("")

            # 完整报告和评分标准说明
            issue_body_lines.extend([
                "## 📄 完整报告与评分标准",
                "",
                "### 详细报告",
                "",
                f"查看更详细的报告请访问仓库的 `reports/` 目录。",
                "",
                "### 评分标准说明",
                "",
                "**综合评分等级**:",
                "",
                "| 分数范围 | 等级 | 说明 |",
                "| --- | --- | --- |",
                "| >80 | 优秀 | 代码质量高，测试覆盖充分，文档完善，安全合规，影响范围和价值突出 |",
                "| 60-80 | 良好 | 整体质量较高，有少量改进空间 |",
                "| <60 | 一般 | 基本满足要求，但存在明显改进点 |",
                "",
                "**维度评分说明** (0-10分):",
                "",
                "- **代码质量**: 代码风格、可读性、设计模式、最佳实践",
                "- **测试覆盖率**: 单元测试、集成测试、边界情况覆盖",
                "- **文档与可维护性**: 代码注释、文档更新、可维护性",
                "- **合规与安全**: 安全漏洞、合规性、依赖安全",
                "- **影响范围合理性**: 根据PR的重要程度和影响范围匹配度评分。如果PR重要性高且影响范围大，这是合理的；如果PR重要性低但影响范围很大，会增加review难度且不太必要，应该低分。考虑影响范围是否与PR重要程度匹配、向后兼容性、对系统的影响程度",
                "- **PR价值与作用**: PR的核心作用、业务价值、功能重要性、是否解决关键问题",
                "",
                "---",
                f"*此 Issue 由 GitHub Actions 自动创建，分析源仓库: `{source_owner}/{source_repo}`*",
            ])

            issue_labels = output_cfg.get("issue_labels", ["automated", "report"])
            if period == "today":
                issue_labels.append("today")
            elif period == "day":
                issue_labels.append("daily")
            else:  # week
                issue_labels.append("weekly")

            target_client.create_issue(
                title=issue_title,
                body="\n".join(issue_body_lines),
                labels=issue_labels,
            )
            print(f"✅ 已在 {target_repo_full_name} 创建 Issue 通知")
        except Exception as e:
            print(f"?? 创建 Issue 失败: {e}")
    elif create_issue and not target_token:
        print("?? 未配置目标仓库 token，跳过创建 Issue")


if __name__ == "__main__":
    main()
