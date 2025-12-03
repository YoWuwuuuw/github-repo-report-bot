from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class IssueAnalysis:
    number: int
    title: str
    state: str
    labels: List[str]
    created_at: str
    closed_at: Optional[str]
    author: str
    assignees: List[str]
    comments: int
    category: str
    summary: str
    created_in_period: bool = False  # 是否在时间段内创建


@dataclass
class DiscussionAnalysis:
    number: int
    title: str
    state: str
    labels: List[str]
    created_at: str
    updated_at: str
    author: str
    comments: int
    category: str
    summary: str
    ai_summary: str
    created_in_period: bool = False  # 是否在时间段内创建


@dataclass
class PRAnalysis:
    number: int
    title: str
    state: str
    labels: List[str]
    created_at: str
    merged_at: Optional[str]
    author: str
    changed_files: int
    additions: int
    deletions: int
    commits: int
    pr_type: str
    size_category: str
    priority: str
    type_score: int
    size_score: int
    code_quality_score: int
    test_coverage_score: int
    doc_maintain_score: int
    compliance_security_score: int
    merge_history_score: int
    collaboration_score: int
    total_score: float
    rating: str
    qwen_comment: str


def _classify_issue_category(title: str, body: str, labels: List[str]) -> str:
    text = f"{title}\n{body}".lower()
    label_text = " ".join(labels).lower()
    if "bug" in label_text or "bug" in text or "error" in text or "fix" in text:
        return "bug"
    if "feature" in label_text or "enhancement" in label_text or "feat" in text or "request" in text:
        return "feature request"
    if "question" in label_text or "how to" in text or "help" in label_text:
        return "question"
    return "other"


def _summarize_issue(title: str, body: str, max_len: int = 200) -> str:
    """提取 Issue 摘要，移除模板文字"""
    # 移除常见的模板文字
    template_patterns = [
        r"### Check Ahead.*?###",
        r"### 检查清单.*?###",
        r"\[x\] I have searched.*?###",
        r"### Environment.*?###",
        r"### Description.*?###",
    ]
    import re
    cleaned_body = body or ""
    for pattern in template_patterns:
        cleaned_body = re.sub(pattern, "", cleaned_body, flags=re.DOTALL | re.IGNORECASE)

    # 组合标题和清理后的正文
    text = (title or "") + " " + cleaned_body
    text = " ".join(text.split())

    # 如果文本太短或包含模板残留，返回标题
    if len(text.strip()) < 20 or "check ahead" in text.lower() or "searched the issues" in text.lower():
        return title[:max_len] + ("..." if len(title) > max_len else "")

    return text[:max_len] + ("..." if len(text) > max_len else "")


def analyze_discussions(
    raw_discussions: List[Dict[str, Any]],
    qwen_client: Any = None
) -> List[DiscussionAnalysis]:
    """分析 Discussions，使用 AI 生成摘要"""
    results: List[DiscussionAnalysis] = []
    for disc in raw_discussions:
        labels = [lbl.get("name", "") for lbl in disc.get("labels", [])]
        category = disc.get("category", "") or "general"
        summary = _summarize_issue(
            disc.get("title", "") or "",
            disc.get("body", "") or "",
        )

        # AI 生成简单解释
        ai_summary = ""
        if qwen_client and qwen_client.api_key:
            try:
                context = f"标题: {disc.get('title', '')}\n内容: {disc.get('body', '')[:500]}"
                ai_result = qwen_client.analyze_discussion(context)
                ai_summary = ai_result.get("summary", "") or ai_result.get("comment", "")
            except Exception:
                pass

        created_in_period = disc.get("_created_in_period", False)
        results.append(
            DiscussionAnalysis(
                number=disc.get("number", 0),
                title=disc.get("title", ""),
                state=disc.get("state", "open"),
                labels=labels,
                created_at=disc.get("created_at", ""),
                updated_at=disc.get("updated_at", ""),
                author=disc.get("user", {}).get("login", ""),
                comments=disc.get("comments", 0),
                category=category,
                summary=summary,
                ai_summary=ai_summary[:300] if ai_summary else "",  # 限制长度
                created_in_period=created_in_period,
            )
        )
    return results


def analyze_issues(raw_issues: List[Dict[str, Any]], qwen_client: Any = None) -> List[IssueAnalysis]:
    """分析 Issues，使用 AI 生成摘要"""
    results: List[IssueAnalysis] = []
    for issue in raw_issues:
        labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
        category = _classify_issue_category(
            issue.get("title", "") or "",
            issue.get("body", "") or "",
            labels,
        )

        # 先清理模板文字
        raw_summary = _summarize_issue(
            issue.get("title", "") or "",
            issue.get("body", "") or "",
        )

        # 使用 AI 生成更好的摘要
        summary = raw_summary
        if qwen_client and qwen_client.api_key:
            try:
                context = f"标题: {issue.get('title', '')}\n内容: {issue.get('body', '')[:800]}"
                ai_result = qwen_client.analyze_issue_summary(context)
                ai_summary = ai_result.get("summary", "") or ai_result.get("comment", "")
                if ai_summary and ai_summary.strip() and not ai_summary.startswith("调用 Qwen 失败"):
                    summary = ai_summary[:200]  # 限制长度
            except Exception:
                pass  # 如果 AI 分析失败，使用原始摘要

        created_at = issue.get("created_at") or ""
        closed_at = issue.get("closed_at")
        created_in_period = issue.get("_created_in_period", False)
        results.append(
            IssueAnalysis(
                number=issue.get("number", 0),
                title=issue.get("title", ""),
                state=issue.get("state", ""),
                labels=labels,
                created_at=created_at,
                closed_at=closed_at,
                author=issue.get("user", {}).get("login", ""),
                assignees=[a.get("login", "") for a in issue.get("assignees", [])],
                comments=issue.get("comments", 0),
                category=category,
                summary=summary,
                created_in_period=created_in_period,
            )
        )
    return results


def _detect_pr_type(title: str, body: str, labels: List[str]) -> str:
    text = f"{title}\n{body}".lower()
    label_text = " ".join(labels).lower()
    if "feat" in text or "feature" in text or "enhancement" in label_text:
        return "feat"
    if "fix" in text or "bug" in label_text:
        return "fix"
    if "refactor" in text or "opt" in text or "optimization" in text:
        return "opt"
    if "test" in label_text or "test" in text:
        return "test"
    if "doc" in label_text or "docs" in text:
        return "docs"
    return "other"


def _type_score(pr_type: str) -> int:
    mapping = {
        "feat": 10,
        "opt": 8,
        "fix": 6,
        "test": 4,
        "docs": 5,
    }
    return mapping.get(pr_type, 5)


def _size_category_and_score(additions: int, deletions: int) -> tuple[str, int]:
    lines = additions + deletions
    if lines < 50:
        return "small", 5
    if lines <= 200:
        return "medium", 7
    return "large", 9


def _priority(pr_type: str) -> str:
    if pr_type == "feat":
        return "P1"
    if pr_type == "opt":
        return "P2"
    if pr_type in {"fix", "docs"}:
        return "P3"
    if pr_type == "test":
        return "P4"
    return "P3"


def _calc_total_score(
    type_score: int,
    size_score: int,
    code_quality_score: int,
    test_coverage_score: int,
    doc_maintain_score: int,
    compliance_security_score: int,
    merge_history_score: int,
    collaboration_score: int,
) -> float:
    """计算综合评分：基础质量维度各15%，价值评估维度各15%，类型和规模各5%"""
    weights = {
        "type": 0.05,      # PR类型（辅助参考）
        "size": 0.05,      # 规模（辅助参考）
        "code": 0.15,      # 代码质量（基础质量维度，一视同仁）
        "test": 0.15,      # 测试覆盖率（基础质量维度，一视同仁）
        "doc": 0.15,       # 文档与可维护性（基础质量维度，一视同仁）
        "security": 0.15,  # 合规与安全（基础质量维度，一视同仁）
        "merge": 0.15,     # 影响范围合理性（价值评估维度，更重要）
        "collab": 0.15,    # PR价值与作用（价值评估维度，更重要）
    }
    total = 0.0
    total += type_score * 10 * weights["type"]
    total += size_score * 10 * weights["size"]
    total += code_quality_score * 10 * weights["code"]
    total += test_coverage_score * 10 * weights["test"]
    total += doc_maintain_score * 10 * weights["doc"]
    total += compliance_security_score * 10 * weights["security"]
    total += merge_history_score * 10 * weights["merge"]
    total += collaboration_score * 10 * weights["collab"]
    return round(total, 1)


def _rating(total_score: float) -> str:
    if total_score > 80:
        return "优秀"
    if total_score > 60:
        return "良好"
    return "一般"


def _clean_references(text: str) -> str:
    """清理 GitHub 引用格式（#123、owner/repo#123），转换为纯文本，避免 AI 生成链接"""
    import re
    # 匹配各种引用格式：#123、owner/repo#123、apache#123、issue #123、PR #123 等
    # 替换为纯文本格式：Issue-123、PR-123
    patterns = [
        (r'(\w+)#(\d+)', r'\1-\2'),  # apache#123 -> apache-123
        (r'#(\d+)', r'Item-\1'),  # #123 -> Item-123（通用格式，避免被识别为链接）
        (r'issue\s+#(\d+)', r'Issue-\1', re.IGNORECASE),  # issue #123 -> Issue-123
        (r'pr\s+#(\d+)', r'PR-\1', re.IGNORECASE),  # PR #123 -> PR-123
        (r'pull\s+request\s+#(\d+)', r'PR-\1', re.IGNORECASE),  # pull request #123 -> PR-123
        (r'discussion\s+#(\d+)', r'Discussion-\1', re.IGNORECASE),  # discussion #123 -> Discussion-123
    ]
    cleaned = text
    for pattern in patterns:
        if isinstance(pattern, tuple) and len(pattern) == 3:
            cleaned = re.sub(pattern[0], pattern[1], cleaned, flags=pattern[2])
        elif isinstance(pattern, tuple):
            cleaned = re.sub(pattern[0], pattern[1], cleaned)
    return cleaned


def build_pr_context(pr: Dict[str, Any]) -> str:
    """构建 PR 上下文，用于 AI 分析"""
    title = pr.get("title", "")
    body = pr.get("body", "") or "无描述"
    # 清理 body 中的引用格式
    body = _clean_references(body)
    user = pr.get('user', {})
    author = user.get('login', 'unknown')

    # 检测PR类型和WIP状态
    labels = pr.get('labels', [])
    label_names = [l.get('name', '') for l in labels]
    pr_type = _detect_pr_type(title, body, label_names)
    is_wip = (
        'wip' in title.lower() or
        'wip' in body.lower() or
        'wip' in ' '.join(label_names).lower() or
        title.strip().startswith('WIP') or
        title.strip().startswith('[WIP]')
    )

    base_info = f"## Pull Request 信息\n\n"
    base_info += f"**标题**: {title}\n"
    base_info += f"**作者**: {author}\n"
    base_info += f"**PR类型**: {pr_type}\n"
    if is_wip:
        base_info += f"**状态**: WIP (进行中) - 请基于预期价值和重要性评分，不要因为未完成而评分过低\n"
    else:
        base_info += f"**状态**: {pr.get('state', 'unknown')}"
        if pr.get('merged_at'):
            base_info += f" (已合并于 {pr.get('merged_at', '')})"
    base_info += "\n"
    base_info += f"**创建时间**: {pr.get('created_at', 'unknown')}\n"
    if pr.get('updated_at'):
        base_info += f"**更新时间**: {pr.get('updated_at')}\n"

    base_info += f"\n**代码变更统计**:\n"
    base_info += f"- 变更文件数: {pr.get('changed_files', 0)}\n"
    base_info += f"- 新增代码行: +{pr.get('additions', 0)}\n"
    base_info += f"- 删除代码行: -{pr.get('deletions', 0)}\n"
    base_info += f"- 提交次数: {pr.get('commits', 0)}\n"

    # 添加评论和审查信息
    base_info += f"- 评论数: {pr.get('comments', 0)}\n"
    if pr.get('review_comments'):
        base_info += f"- 代码审查评论数: {pr.get('review_comments', 0)}\n"

    base_info += f"\n**PR 描述**:\n{body}\n\n"

    # 文件改动详情
    files = pr.get("files_list", [])
    if files:
        base_info += "## 文件改动详情\n\n"
        # 按变更类型分类
        added_files = []
        modified_files = []
        deleted_files = []

        for f in files[:50]:  # 最多显示50个文件
            status = f.get('status', 'modified')
            filename = f.get('filename', '')
            additions = f.get('additions', 0)
            deletions = f.get('deletions', 0)
            changes = additions + deletions

            file_info = f"- `{filename}`"
            if status == 'added':
                file_info += f" (新增, +{additions} 行)"
                added_files.append(file_info)
            elif status == 'removed':
                file_info += f" (删除, -{deletions} 行)"
                deleted_files.append(file_info)
            else:
                file_info += f" (修改, +{additions}/-{deletions}, 共 {changes} 行变更)"
                modified_files.append(file_info)

        if added_files:
            base_info += "### 新增文件:\n"
            base_info += "\n".join(added_files[:20]) + "\n\n"
        if modified_files:
            base_info += "### 修改文件:\n"
            base_info += "\n".join(modified_files[:30]) + "\n\n"
        if deleted_files:
            base_info += "### 删除文件:\n"
            base_info += "\n".join(deleted_files[:10]) + "\n\n"

        # 统计信息
        total_changes = sum(f.get('additions', 0) + f.get('deletions', 0) for f in files)
        base_info += f"**总计**: {len(files)} 个文件，{total_changes} 行代码变更\n\n"

    # 添加标签信息
    if labels:
        base_info += f"**标签**: {', '.join(label_names)}\n\n"

    # 添加PR类型和价值提示
    base_info += "**评分提示**:\n"
    if pr_type in ['feat', 'opt']:
        base_info += f"- 这是{pr_type}类型的PR，通常价值较高，如果重要性高且影响范围大是合理的\n"
    elif pr_type in ['test', 'docs']:
        base_info += f"- 这是{pr_type}类型的PR，价值相对较低，如果影响范围很大但重要性低，应该低分（会增加review难度且不太必要）\n"
    if is_wip:
        base_info += "- 这是WIP PR，请基于预期价值和重要性评分，重点关注实现后的效果\n"

    base_info += "---\n\n"
    base_info += "请基于以上信息，重点关注PR的价值、重要性和影响范围合理性进行专业评估。"

    return base_info


def analyze_pull_requests(
    raw_pr_details: List[Dict[str, Any]],
    qwen_results: Dict[int, Dict[str, Any]],
) -> List[PRAnalysis]:
    results: List[PRAnalysis] = []
    for pr in raw_pr_details:
        labels = [lbl.get("name", "") for lbl in pr.get("labels", [])]
        pr_type = _detect_pr_type(
            pr.get("title", "") or "",
            pr.get("body", "") or "",
            labels,
        )
        type_score = _type_score(pr_type)
        size_category, size_score = _size_category_and_score(
            pr.get("additions", 0) or 0,
            pr.get("deletions", 0) or 0,
        )
        priority = _priority(pr_type)

        qwen_data = qwen_results.get(pr.get("number", 0), {}) or {}
        code_quality_score = int(qwen_data.get("code_quality_score", 0))
        test_coverage_score = int(qwen_data.get("test_coverage_score", 0))
        doc_maintain_score = int(qwen_data.get("doc_maintain_score", 0))
        compliance_security_score = int(
            qwen_data.get("compliance_security_score", 0)
        )
        merge_history_score = int(qwen_data.get("merge_history_score", 0))
        collaboration_score = int(qwen_data.get("collaboration_score", 0))
        comment = str(qwen_data.get("comment", ""))[:500]

        total_score = _calc_total_score(
            type_score=type_score,
            size_score=size_score,
            code_quality_score=code_quality_score,
            test_coverage_score=test_coverage_score,
            doc_maintain_score=doc_maintain_score,
            compliance_security_score=compliance_security_score,
            merge_history_score=merge_history_score,
            collaboration_score=collaboration_score,
        )

        results.append(
            PRAnalysis(
                number=pr.get("number", 0),
                title=pr.get("title", ""),
                state=pr.get("state", ""),
                labels=labels,
                created_at=pr.get("created_at", ""),
                merged_at=pr.get("merged_at"),
                author=pr.get("user", {}).get("login", ""),
                changed_files=pr.get("changed_files", 0) or 0,
                additions=pr.get("additions", 0) or 0,
                deletions=pr.get("deletions", 0) or 0,
                commits=pr.get("commits", 0) or 0,
                pr_type=pr_type,
                size_category=size_category,
                priority=priority,
                type_score=type_score,
                size_score=size_score,
                code_quality_score=code_quality_score,
                test_coverage_score=test_coverage_score,
                doc_maintain_score=doc_maintain_score,
                compliance_security_score=compliance_security_score,
                merge_history_score=merge_history_score,
                collaboration_score=collaboration_score,
                total_score=total_score,
                rating=_rating(total_score),
                qwen_comment=comment,
            )
        )
    return results



