import os
import time
from typing import Any, Dict, Optional

import requests


class QwenClient:
    """Qwen AI 客户端，用于 PR 质量分析和评分"""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        model: str,
        max_requests_per_minute: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        self.model = model
        self.max_requests_per_minute = max_requests_per_minute
        self._request_timestamps = []

    def _throttle(self) -> None:
        now = time.time()
        self._request_timestamps = [
            ts for ts in self._request_timestamps if now - ts < 60
        ]
        if len(self._request_timestamps) >= self.max_requests_per_minute:
            sleep_sec = 60 - (now - self._request_timestamps[0]) + 1
            if sleep_sec > 0:
                time.sleep(sleep_sec)
        self._request_timestamps.append(time.time())

    def analyze_pr(self, pr_context: str) -> Dict[str, Any]:
        """使用 Qwen 分析 PR，返回各维度评分（0-10分）和详细建议"""
        if not self.api_key:
            return {
                "code_quality_score": 0,
                "test_coverage_score": 0,
                "doc_maintain_score": 0,
                "compliance_security_score": 0,
                "merge_history_score": 0,
                "collaboration_score": 0,
                "comment": "Qwen API key 未配置，未实际调用模型。",
            }

        self._throttle()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位资深的代码评审专家，擅长分析 Pull Request 的质量、价值和重要性。"
                        "请仔细分析 PR 的代码变更、类型、影响范围、解决的问题等方面，"
                        "对以下维度进行 0-10 分的评分：\n\n"
                        "**评分维度说明**：\n\n"
                        "**基础质量维度**（前四个维度一视同仁，客观评价）：\n"
                        "- code_quality_score: 代码质量（代码风格、可读性、设计模式、最佳实践）\n"
                        "- test_coverage_score: 测试覆盖率（单元测试、集成测试、边界情况覆盖）\n"
                        "- doc_maintain_score: 文档与可维护性（代码注释、文档更新、可维护性）\n"
                        "- compliance_security_score: 合规与安全（安全漏洞、合规性、依赖安全）\n\n"
                        "**价值评估维度**（根据PR类型和实际情况评分）：\n"
                        "- merge_history_score: 影响范围合理性（根据PR的重要程度和影响范围匹配度评分。"
                        "如果PR重要性高且影响范围大，这是合理的；如果PR重要性低但影响范围很大，"
                        "会增加review难度且不太必要，应该低分。"
                        "考虑：影响范围是否与PR重要程度匹配、向后兼容性、对系统的影响程度）\n"
                        "- collaboration_score: PR价值与作用（根据PR类型和重要程度评分：feat/opt通常价值更高，"
                        "fix根据问题严重程度，test/doc价值相对较低。"
                        "同时考虑：解决的问题的重要性和紧急程度、业务价值、功能重要性、是否解决关键问题）\n\n"
                        "**特殊说明**：\n"
                        "- 如果PR标记为WIP（Work In Progress），不要因为未完成而评分过低，"
                        "主要分析PR的重要性和预计实现后的效果，基于预期价值评分\n"
                        "- 对于重要性低但影响范围大的PR（如简单的doc/test修改却涉及大量文件），"
                        "影响范围合理性应该低分，因为会增加review难度且不太必要\n"
                        "- 对于重要性高且影响范围大的PR（如重要feat/opt），如果价值匹配，应该给予高分\n\n"
                        "**comment 字段要求**（详细、分段、可读性强）：\n"
                        "请提供详细的分析建议，包含以下内容（分段输出，每段之间用空行分隔）：\n"
                        "1. **核心价值**：PR的核心价值和重要性（2-3句话）\n"
                        "2. **关键亮点**：代码质量、设计、实现等方面的亮点（2-3句话）\n"
                        "3. **改进建议**：最值得关注的1-2个关键改进点或建议（如果有，否则省略，1-2句话）\n"
                        "4. **整体评价**：对PR的整体评价和预期影响（1-2句话）\n"
                        "总字数控制在200-300字，要详细、专业、有建设性，分段输出以增强可读性。\n\n"
                        "**重要：禁止生成链接**：\n"
                        "- 绝对不要使用 Markdown 链接格式，如 `[文本](url)` 或 `[#123](url)`\n"
                        "- 绝对不要使用 GitHub 引用格式，如 `#123`、`owner/repo#123`、`issue #123`、`PR #123`、`apache#123` 等\n"
                        "- 如果需要提及 Issue、PR 或 Discussion，请使用纯文本格式，如：`Issue-123`、`PR-123`、`Discussion-123`（注意使用连字符，不要使用井号）\n"
                        "- 不要生成任何形式的链接或引用，只使用纯文本描述"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请分析以下 Pull Request，重点关注PR的价值、重要性和影响范围合理性：\n\n"
                        f"{pr_context}\n\n"
                        "请返回 JSON 格式，包含所有评分字段（0-10分）和详细的 comment。"
                        "comment 需要详细、分段输出，控制在200-300字，包含核心价值、关键亮点、改进建议、整体评价等内容。"
                        "如果是WIP PR，基于预期价值评分，不要因为未完成而评分过低。\n\n"
                        "**严格禁止**：不要使用任何链接格式（如 `[#123](url)`、`#123`、`apache#123` 等），"
                        "如需提及 Issue/PR/Discussion，请使用纯文本格式如 `Issue-123`、`PR-123`（使用连字符，不用井号）。"
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "{}")
            )
            import json

            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            return {
                "code_quality_score": 0,
                "test_coverage_score": 0,
                "doc_maintain_score": 0,
                "compliance_security_score": 0,
                "merge_history_score": 0,
                "collaboration_score": 0,
                "comment": f"调用 Qwen 失败：{exc}",
            }

    def analyze_discussion(self, discussion_context: str) -> Dict[str, Any]:
        """分析 Discussion，返回简要总结"""
        if not self.api_key:
            return {
                "summary": "Qwen API key 未配置，未实际调用模型。",
            }

        self._throttle()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位技术社区分析专家，擅长总结和解释技术讨论的核心内容。"
                        "请用简洁、专业的中文总结 Discussion 的核心观点、问题或建议，"
                        "控制在 100 字以内。\n\n"
                        "**重要：禁止生成链接**：\n"
                        "- 绝对不要使用 Markdown 链接格式，如 `[文本](url)` 或 `[#123](url)`\n"
                        "- 绝对不要使用 GitHub 引用格式，如 `#123`、`owner/repo#123`、`issue #123`、`PR #123` 等\n"
                        "- 如果需要提及 Issue、PR 或 Discussion，请使用纯文本格式，如：`Issue-123`、`PR-123`、`Discussion-123`（注意使用连字符，不要使用井号）\n"
                        "- 不要生成任何形式的链接或引用，只使用纯文本描述"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请简要总结以下 Discussion 的核心内容：\n\n"
                        f"{discussion_context}\n\n"
                        "请返回 JSON 格式，包含 summary 字段（简要总结，100字以内）。\n\n"
                        "**严格禁止**：不要使用任何链接格式（如 `[#123](url)`、`#123`、`apache#123` 等），"
                        "如需提及 Issue/PR/Discussion，请使用纯文本格式如 `Issue-123`、`PR-123`（使用连字符，不用井号）。"
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "{}")
            )
            import json

            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            return {
                "summary": f"调用 Qwen 失败：{exc}",
            }

    def analyze_issue_summary(self, issue_context: str) -> Dict[str, Any]:
        """分析 Issue，生成核心问题摘要"""
        if not self.api_key:
            return {
                "summary": "",
            }

        self._throttle()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位技术问题分析专家，擅长提取 Issue 的核心问题。"
                        "请用简洁、专业的中文总结 Issue 的核心问题、错误信息或需求，"
                        "移除所有模板文字（如 'Check Ahead'、'I have searched' 等），"
                        "控制在 150 字以内，只保留真正的问题描述。\n\n"
                        "**重要：禁止生成链接**：\n"
                        "- 绝对不要使用 Markdown 链接格式，如 `[文本](url)` 或 `[#123](url)`\n"
                        "- 绝对不要使用 GitHub 引用格式，如 `#123`、`owner/repo#123`、`issue #123`、`PR #123` 等\n"
                        "- 如果需要提及 Issue、PR 或 Discussion，请使用纯文本格式，如：`Issue-123`、`PR-123`、`Discussion-123`（注意使用连字符，不要使用井号）\n"
                        "- 不要生成任何形式的链接或引用，只使用纯文本描述"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请提取以下 Issue 的核心问题，移除模板文字：\n\n"
                        f"{issue_context}\n\n"
                        "请返回 JSON 格式，包含 summary 字段（核心问题摘要，150字以内，不要包含模板文字）。\n\n"
                        "**严格禁止**：不要使用任何链接格式（如 `[#123](url)`、`#123`、`apache#123` 等），"
                        "如需提及 Issue/PR/Discussion，请使用纯文本格式如 `Issue-123`、`PR-123`（使用连字符，不用井号）。"
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "{}")
            )
            import json

            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            return {
                "summary": "",
            }


