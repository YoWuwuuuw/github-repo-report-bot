from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from .analyzer import IssueAnalysis, PRAnalysis, DiscussionAnalysis

# 北京时间时区（UTC+8）
BEIJING_TZ = timezone(timedelta(hours=8))


def _ts() -> str:
    return datetime.now(timezone.utc).astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S") + " (北京时间)"


def generate_markdown_report(
    repo_full_name: str,
    issues: List[IssueAnalysis],
    prs: List[PRAnalysis],
    discussions: List[DiscussionAnalysis],
    report_dir: Path,
    period: str = "day",
    period_label: str = "",
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_path = report_dir / f"report-{ts_slug}.md"

    lines: list[str] = []
    period_display = "每日" if period == "day" else "每周"
    lines.append(f"# {period_display}分析报告 - {repo_full_name}")
    lines.append("")
    lines.append(f"- **生成时间**: {_ts()}")
    if period_label:
        lines.append(f"- **时间维度**: {period_label}")
    if period_start and period_end:
        period_start_bj = period_start.astimezone(BEIJING_TZ)
        period_end_bj = period_end.astimezone(BEIJING_TZ)
        lines.append(f"- **时间范围**: {period_start_bj.strftime('%Y-%m-%d %H:%M:%S')} 至 {period_end_bj.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    lines.append(f"- **Issue 数量**: {len(issues)}")
    lines.append(f"- **PR 数量**: {len(prs)}")
    lines.append(f"- **Discussion 数量**: {len(discussions)}")
    lines.append("")

    if prs:
        lines.append("## Pull Request 概要")
        lines.append("")
        lines.append(
            "| 编号 | 标题 | 作者 | 类型 | 优先级 | 规模 | 总分 | 评级 | 状态 |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
        )
        for pr in sorted(prs, key=lambda x: x.total_score, reverse=True):
            lines.append(
                f"| PR-{pr.number} | {pr.title[:40]} | {pr.author} | {pr.pr_type} | "
                f"{pr.priority} | {pr.size_category} | {pr.total_score} | {pr.rating} | {pr.state} |"
            )
        lines.append("")

    if issues:
        lines.append("## Issue 概要")
        lines.append("")
        lines.append(
            "| 编号 | 标题 | 作者 | 状态 | 分类 | 评论数 | 创建时间 |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- | --- |"
        )
        for it in issues:
            lines.append(
                f"| Issue-{it.number} | {it.title[:40]} | {it.author} | {it.state} | "
                f"{it.category} | {it.comments} | {it.created_at[:10]} |"
            )
        lines.append("")

    if prs:
        lines.append("## PR 详细分析")
        for pr in sorted(prs, key=lambda x: x.total_score, reverse=True):
            lines.append("")
            lines.append(f"### PR-{pr.number} - {pr.title}")
            lines.append("")
            lines.append(f"- 作者：{pr.author}")
            lines.append(f"- 状态：{pr.state}（merged: {bool(pr.merged_at)}）")
            lines.append(f"- 创建时间：{pr.created_at}")
            lines.append(f"- 变更文件数：{pr.changed_files}")
            lines.append(f"- 新增 / 删除行：+{pr.additions} / -{pr.deletions}")
            lines.append(f"- 提交次数：{pr.commits}")
            lines.append(f"- 类型：{pr.pr_type}，优先级：{pr.priority}")
            lines.append(f"- 规模：{pr.size_category}")
            lines.append("")
            lines.append("**维度评分（0-10）：**")
            lines.append(
                f"- 提交类型：{pr.type_score}"
            )
            lines.append(f"- 改动规模：{pr.size_score}")
            lines.append(f"- 代码质量：{pr.code_quality_score}")
            lines.append(f"- 测试覆盖率：{pr.test_coverage_score}")
            lines.append(
                f"- 文档与可维护性：{pr.doc_maintain_score}"
            )
            lines.append(
                f"- 合规与安全：{pr.compliance_security_score}"
            )
            lines.append(f"- 影响范围合理性：{pr.merge_history_score}")
            lines.append(f"- PR价值与作用：{pr.collaboration_score}")
            lines.append("")
            lines.append(f"**综合评分：{pr.total_score} （{pr.rating}）**")
            lines.append("")
            if pr.qwen_comment:
                lines.append("**Qwen 建议：**")
                lines.append("")
                lines.append(pr.qwen_comment)
                lines.append("")

    if issues:
        lines.append("## Issue 详细列表")
        for it in issues:
            lines.append("")
            lines.append(f"### Issue-{it.number} - {it.title}")
            lines.append("")
            lines.append(f"- 作者：{it.author}")
            lines.append(f"- 状态：{it.state}")
            lines.append(f"- 分类：{it.category}")
            lines.append(f"- 标签：{', '.join(it.labels) if it.labels else '无'}")
            lines.append(f"- 评论数：{it.comments}")
            lines.append(f"- 创建时间：{it.created_at}")
            if it.closed_at:
                lines.append(f"- 关闭时间：{it.closed_at}")
            lines.append("")
            lines.append(f"摘要：{it.summary}")

    if discussions:
        lines.append("## Discussion 详细列表")
        # 区分时间段内创建的 Discussion 和有动静的 Discussion
        created_discussions = [d for d in discussions if d.created_in_period]
        updated_discussions = [d for d in discussions if not d.created_in_period]

        if created_discussions:
            lines.append("")
            lines.append("### 📅 时间段内创建的 Discussion")
            for disc in sorted(created_discussions, key=lambda x: x.number, reverse=True):
                lines.append("")
                lines.append(f"### Discussion-{disc.number} - {disc.title}")
                lines.append("")
                lines.append(f"- 作者：{disc.author}")
                lines.append(f"- 状态：{disc.state}")
                lines.append(f"- 分类：{disc.category}")
                lines.append(f"- 标签：{', '.join(disc.labels) if disc.labels else '无'}")
                lines.append(f"- 评论数：{disc.comments}")
                lines.append(f"- 创建时间：{disc.created_at}")
                if disc.updated_at:
                    lines.append(f"- 更新时间：{disc.updated_at}")
                lines.append("")
                lines.append(f"摘要：{disc.summary}")
                if disc.ai_summary:
                    lines.append(f"AI 摘要：{disc.ai_summary}")

        if updated_discussions:
            lines.append("")
            lines.append("### 🔄 时间段内有动静的 Discussion")
            for disc in sorted(updated_discussions, key=lambda x: x.number, reverse=True):
                lines.append("")
                lines.append(f"### Discussion-{disc.number} - {disc.title}")
                lines.append("")
                lines.append(f"- 作者：{disc.author}")
                lines.append(f"- 状态：{disc.state}")
                lines.append(f"- 分类：{disc.category}")
                lines.append(f"- 标签：{', '.join(disc.labels) if disc.labels else '无'}")
                lines.append(f"- 评论数：{disc.comments}")
                lines.append(f"- 创建时间：{disc.created_at}")
                if disc.updated_at:
                    lines.append(f"- 更新时间：{disc.updated_at}")
                lines.append("")
                lines.append(f"摘要：{disc.summary}")
                if disc.ai_summary:
                    lines.append(f"AI 摘要：{disc.ai_summary}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path




