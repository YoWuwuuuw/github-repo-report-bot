import os
from typing import Any, Dict, List, Optional

import requests


class GitHubClient:
    """GitHub API 客户端，支持读取 Issue/PR/Discussion 和创建 Issue"""

    def __init__(
        self,
        owner: str,
        repo: str,
        token: Optional[str] = None,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token or os.getenv("GH_TOKEN")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "github-repo-report-bot",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """发送 GET 请求到 GitHub API"""
        url = f"{self.base_url}{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Any:
        """发送 POST 请求到 GitHub API"""
        url = f"{self.base_url}{endpoint}"
        resp = requests.post(url, headers=self.headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, endpoint: str, data: Dict[str, Any]) -> Any:
        """发送 PATCH 请求到 GitHub API"""
        url = f"{self.base_url}{endpoint}"
        resp = requests.patch(url, headers=self.headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_issues(
        self,
        state: str = "all",
        since: Optional[str] = None,
        max_count: int = 300,
    ) -> List[Dict[str, Any]]:
        """获取 Issue 列表（过滤 PR）"""
        params: Dict[str, Any] = {
            "state": state,
            "per_page": min(100, max_count),
            "page": 1,
        }
        if since:
            params["since"] = since

        all_issues: List[Dict[str, Any]] = []
        while len(all_issues) < max_count:
            issues = self._get(
                f"/repos/{self.owner}/{self.repo}/issues", params=params
            )
            if not issues:
                break
            # 过滤 PR（GitHub API 的 /issues 端点同时返回 PR）
            issues = [i for i in issues if "pull_request" not in i]
            all_issues.extend(issues[: max_count - len(all_issues)])
            if len(issues) < params["per_page"]:
                break
            params["page"] += 1

        return all_issues[:max_count]

    def list_pull_requests(
        self,
        state: str = "all",
        max_count: int = 200,
    ) -> List[Dict[str, Any]]:
        """获取 Pull Request 列表"""
        params: Dict[str, Any] = {
            "state": state,
            "per_page": min(100, max_count),
            "page": 1,
        }

        all_prs: List[Dict[str, Any]] = []
        while len(all_prs) < max_count:
            prs = self._get(
                f"/repos/{self.owner}/{self.repo}/pulls", params=params
            )
            if not prs:
                break
            all_prs.extend(prs[: max_count - len(all_prs)])
            if len(prs) < params["per_page"]:
                break
            params["page"] += 1

        return all_prs[:max_count]

    def get_pull_request_detail(self, number: int) -> Dict[str, Any]:
        """获取 PR 详细信息（包含文件变更列表）"""
        pr = self._get(f"/repos/{self.owner}/{self.repo}/pulls/{number}")
        files = self._get(f"/repos/{self.owner}/{self.repo}/pulls/{number}/files")
        pr["files_list"] = files

        return pr

    def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """创建新的 Issue，支持设置标签"""
        if not self.token:
            raise ValueError("需要 GH_TOKEN 才能创建 Issue")

        data: Dict[str, Any] = {
            "title": title,
            "body": body,
        }
        # 确保 labels 是列表且不为空
        if labels:
            # 过滤空字符串和 None
            valid_labels = [label for label in labels if label and isinstance(label, str)]
            if valid_labels:
                data["labels"] = valid_labels
                print(f"   设置 Issue 标签: {', '.join(valid_labels)}")

        result = self._post(f"/repos/{self.owner}/{self.repo}/issues", data=data)

        # 检查标签是否成功设置，如果没有则尝试单独添加
        if labels and result.get("number"):
            issue_number = result.get("number")
            valid_labels = [label for label in labels if label and isinstance(label, str)]
            if valid_labels:
                # 检查返回的 Issue 是否已有标签
                result_labels = [lbl.get("name", "") for lbl in result.get("labels", [])]
                missing_labels = set(valid_labels) - set(result_labels)

                if missing_labels:
                    try:
                        # 使用 POST 方法添加缺失的标签
                        labels_data = {"labels": list(missing_labels)}
                        self._post(f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels", data=labels_data)
                        print(f"   已为 Issue #{issue_number} 添加标签: {', '.join(missing_labels)}")
                    except Exception as e:
                        print(f"   ⚠️  添加标签失败: {e}，Issue 已创建但可能没有标签")
                else:
                    print(f"   ✅ Issue #{issue_number} 标签已设置: {', '.join(valid_labels)}")

        return result

    def list_discussions(
        self,
        since: Optional[str] = None,
        max_count: int = 100,
    ) -> List[Dict[str, Any]]:
        """使用 GraphQL API 获取 Discussion 列表"""
        if not self.token:
            return []

        query = """
        query($owner: String!, $repo: String!, $first: Int!, $after: String) {
            repository(owner: $owner, name: $repo) {
                discussions(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        number
                        title
                        body
                        state
                        createdAt
                        updatedAt
                        author {
                            login
                        }
                        comments {
                            totalCount
                        }
                        category {
                            name
                        }
                        labels(first: 10) {
                            nodes {
                                name
                            }
                        }
                    }
                }
            }
        }
        """

        all_discussions: List[Dict[str, Any]] = []
        cursor = None

        try:
            while len(all_discussions) < max_count:
                variables = {
                    "owner": self.owner,
                    "repo": self.repo,
                    "first": min(100, max_count - len(all_discussions)),
                    "after": cursor,
                }

                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "User-Agent": "github-repo-report-bot",
                }

                resp = requests.post(
                    "https://api.github.com/graphql",
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                if "errors" in data:
                    break

                repository = data.get("data", {}).get("repository")
                if not repository:
                    break

                discussions_data = repository.get("discussions", {})
                discussions = discussions_data.get("nodes", [])

                if not discussions:
                    break

                for disc in discussions:
                    if since:
                        created_at = disc.get("createdAt", "")
                        if created_at < since:
                            continue

                    formatted_disc = {
                        "number": disc.get("number", 0),
                        "title": disc.get("title", ""),
                        "body": disc.get("body", ""),
                        "state": "open" if disc.get("state") == "OPEN" else "closed",
                        "created_at": disc.get("createdAt", ""),
                        "updated_at": disc.get("updatedAt", ""),
                        "user": {"login": disc.get("author", {}).get("login", "")},
                        "comments": disc.get("comments", {}).get("totalCount", 0),
                        "labels": [{"name": lbl.get("name", "")} for lbl in disc.get("labels", {}).get("nodes", [])],
                        "category": disc.get("category", {}).get("name", ""),
                    }
                    all_discussions.append(formatted_disc)

                page_info = discussions_data.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break
                cursor = page_info.get("endCursor")

        except Exception:
            pass

        return all_discussions[:max_count]
