"""Tool registry used by the conversation agent to access existing services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class AgentTool:
    name: str
    description: str
    handler: ToolHandler

    async def execute(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        return await self.handler(user_id=user_id, **kwargs)


class ToolRegistry:
    def __init__(self, service: Any) -> None:
        self.service = service
        self._tools: dict[str, AgentTool] = {}
        self._register_defaults()

    def register(self, name: str, description: str, handler: ToolHandler) -> None:
        self._tools[name] = AgentTool(name, description, handler)

    def list(self) -> list[dict[str, str]]:
        return [{"name": tool.name, "description": tool.description} for tool in self._tools.values()]

    async def execute(self, name: str, user_id: str, **kwargs: Any) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"ok": False, "reason": f"unknown tool: {name}"}
        result = await tool.execute(user_id, **kwargs)
        return {"tool": name, "status": "success" if result.get("ok", True) else "failed", "result": result}

    def _register_defaults(self) -> None:
        self.register("get_user_memory", "读取用户画像与长期记忆", self._get_user_memory)
        self.register("search_memory", "检索与问题相关的用户记忆", self._search_memory)
        self.register("save_memory", "保存稳定的长期用户事实", self._save_memory)
        self.register("update_memory", "更新用户画像或当前项目", self._save_memory)
        self.register("get_goals", "读取当前目标", self._get_goals)
        self.register("create_goal", "创建目标", self._create_goal)
        self.register("update_goal", "更新目标", self._update_goal)
        self.register("get_watch_tasks", "读取关注任务", self._get_watch_tasks)
        self.register("create_watch", "创建关注任务", self._create_watch)
        self.register("update_watch", "更新关注任务", self._update_watch)
        self.register("search_knowledge", "检索个人知识库", self._search_knowledge)
        self.register("save_knowledge", "保存个人知识条目", self._save_knowledge)
        self.register("search_latest_content", "检索 Radar 已采集内容", self._search_latest_content)
        self.register("get_recommendations", "读取个性化推荐", self._get_recommendations)
        self.register("list_skills", "列出可用技能", self._list_skills)
        self.register("execute_skill", "执行已注册技能", self._execute_skill)

    async def _get_user_memory(self, user_id: str, **_: Any) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        return {"ok": True, "memory": scope.user_memory.context(), "hierarchy": scope.hierarchy.snapshot()}

    async def _search_memory(self, user_id: str, query: str = "", **_: Any) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        ctx = scope.user_memory.context()
        hierarchy = scope.hierarchy.snapshot()
        rows: list[dict[str, str]] = []
        for item in ctx.get("interests") or []:
            rows.append({"kind": "interest", "text": str(item.get("topic") or "")})
        project = ctx.get("project") or {}
        rows.append({"kind": "project", "text": " ".join([str(project.get("project") or ""), *(project.get("topics") or [])])})
        long_term = hierarchy.get("long_term") or {}
        rows.append({"kind": "long_term", "text": str(long_term.get("profile_summary") or "")})
        for fact in long_term.get("knowledge") or []:
            rows.append({"kind": "fact", "text": str(fact)})
        needle = (query or "").lower().strip()
        matched = [row for row in rows if not needle or any(word in row["text"].lower() for word in needle.split())]
        return {"ok": True, "items": (matched or rows)[:12], "project": project}

    async def _save_memory(
        self,
        user_id: str,
        fact: str = "",
        topics: list[str] | None = None,
        project: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        clean_topics = [str(x).strip() for x in (topics or []) if str(x).strip()]
        if clean_topics:
            scope.user_memory.add_interests(
                [{"topic": topic, "weight": 0.86, "source": ["conversation"]} for topic in clean_topics]
            )
            scope.hierarchy.merge_keywords("work", clean_topics, intent=fact)
        saved_project = scope.user_memory.project()
        if project or clean_topics:
            patch: dict[str, Any] = {}
            if project:
                patch["project"] = project
            if clean_topics:
                patch["topics"] = list(dict.fromkeys(clean_topics + list(saved_project.get("topics") or [])))[:16]
            saved_project = scope.user_memory.save_project(patch)
        if fact:
            scope.hierarchy.add_memory(fact, "已提取为长期记忆", {"action": "memory_extract", "promote": True})
        return {"ok": True, "fact": fact, "topics": clean_topics, "project": saved_project}

    async def _get_goals(self, user_id: str, **_: Any) -> dict[str, Any]:
        return {"ok": True, "items": self.service.for_user(user_id).workspace.goals()}

    async def _create_goal(self, user_id: str, title: str, kind: str = "open", **_: Any) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        items = scope.workspace.goals()
        goal = {
            "id": f"g-{uuid.uuid4().hex[:10]}",
            "kind": kind,
            "title": title.strip(),
            "priority": "medium",
            "progress": 0,
            "linked": 0,
            "done": False,
        }
        items.append(goal)
        scope.workspace.save_goals(items)
        return {"ok": True, "goal": goal}

    async def _update_goal(self, user_id: str, goal_id: str, patch: dict[str, Any], **_: Any) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        items = scope.workspace.goals()
        for goal in items:
            if goal.get("id") == goal_id:
                goal.update(patch)
                scope.workspace.save_goals(items)
                return {"ok": True, "goal": goal}
        return {"ok": False, "reason": "goal not found"}

    async def _get_watch_tasks(self, user_id: str, **_: Any) -> dict[str, Any]:
        items = [
            row for row in self.service.for_user(user_id).user_memory.interests()
            if "follow" in (row.get("source") or []) or "conversation" in (row.get("source") or [])
        ]
        return {"ok": True, "items": items}

    async def _create_watch(self, user_id: str, topics: list[str], **_: Any) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        rows = [{"topic": topic, "weight": 0.9, "source": ["follow", "conversation"]} for topic in topics if topic]
        interests = scope.user_memory.add_interests(rows)
        note = "已开始关注：" + "、".join(row["topic"] for row in rows)
        scope.hierarchy.add_memory(note, "后续重要更新会纳入推荐与推送。", {"action": "follow", "promote": True})
        return {"ok": bool(rows), "topics": [row["topic"] for row in rows], "interests": interests, "note": note}

    async def _update_watch(self, user_id: str, topic: str, weight: float = 0.8, **_: Any) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        interests = scope.user_memory.add_interests([{"topic": topic, "weight": weight, "source": ["follow"]}])
        return {"ok": True, "topic": topic, "interests": interests}

    async def _search_knowledge(self, user_id: str, query: str = "", **_: Any) -> dict[str, Any]:
        rows = self.service.for_user(user_id).memory.cards()
        needle = query.lower().strip()
        if needle:
            rows = [row for row in rows if needle in str(row).lower()]
        return {"ok": True, "items": rows[:10]}

    async def _save_knowledge(self, user_id: str, title: str, content: str, source_url: str = "", **_: Any) -> dict[str, Any]:
        scope = self.service.for_user(user_id)
        card = scope.memory.add_card(
            {
                "title": title.strip() or content[:40],
                "summary": content.strip(),
                "source_url": source_url or f"memory://knowledge/{uuid.uuid4().hex}",
                "tags": ["对话沉淀"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {"ok": True, "card": card}

    async def _search_latest_content(self, user_id: str, query: str = "", **_: Any) -> dict[str, Any]:
        rows = self.service.for_user(user_id).memory.feeds().get("for_you") or []
        needle = query.lower().strip()
        if needle:
            terms = [term for term in needle.split() if len(term) > 1]
            matched = [row for row in rows if any(term in str(row).lower() for term in terms)]
            rows = matched or rows
        return {"ok": True, "items": rows[:8]}

    async def _get_recommendations(self, user_id: str, **_: Any) -> dict[str, Any]:
        rows = self.service.for_user(user_id).memory.feeds().get("for_you") or []
        return {"ok": True, "items": rows[:8]}

    async def _list_skills(self, user_id: str, **_: Any) -> dict[str, Any]:
        return {"ok": True, "items": [], "message": "技能接口已就绪，当前尚未安装外部技能。"}

    async def _execute_skill(self, user_id: str, skill: str = "", **_: Any) -> dict[str, Any]:
        return {"ok": False, "reason": f"技能 {skill or 'unknown'} 尚未安装"}
