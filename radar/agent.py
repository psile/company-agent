"""Intent routing and tool-based planning for the personal secretary agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from . import llm
from .agent_tools import ToolRegistry


INTENTS = {
    "general_chat",
    "search_info",
    "create_watch",
    "update_watch",
    "create_goal",
    "update_goal",
    "save_memory",
    "query_memory",
    "save_knowledge",
    "query_knowledge",
    "change_conversation_setting",
    "execute_skill",
    "unknown",
}

KNOWN_TOPICS = [
    "Agent Memory",
    "多模态长期记忆",
    "长期记忆",
    "Mem0",
    "MemOS",
    "MemoryOS",
    "RAG",
    "Personal Agent",
    "个人 AI 秘书",
    "World Model",
    "Autonomous Driving",
    "VLM",
    "vLLM",
    "Codex",
    "Claude Code",
]


@dataclass
class IntentResult:
    intent: str
    confidence: float
    entities: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "confidence": self.confidence, "entities": self.entities}


class IntentRouter:
    def route(self, message: str) -> IntentResult:
        text = (message or "").strip()
        rules = [
            ("change_conversation_setting", r"(以后|回答|回复|技术问题|普通问题).*(简洁|简短|详细|结论|先问|确认|主动|少推送|少打扰)"),
            ("create_watch", r"(帮我|开始|持续|最近).{0,8}(关注|跟踪|追踪|盯住)"),
            ("update_watch", r"(提高|降低|取消|停止).{0,8}(关注|跟踪|追踪)"),
            ("create_goal", r"(创建|新增|记下|设定).{0,6}(目标|计划)"),
            ("update_goal", r"(完成|更新|修改).{0,6}(目标|计划)"),
            ("query_memory", r"(你记得|还记得|我最近主要(研究|在做)什么|我的偏好是什么|我在研究什么|我主要研究什么)"),
            ("save_memory", r"(记住|请记下|我最近主要(在做|做的是)|我长期|我的偏好是|我通常)"),
            ("save_knowledge", r"(保存|收录|加入).{0,6}(知识库|知识)"),
            ("query_knowledge", r"(查询|搜索|查找|看看).{0,6}(知识库|知识)"),
            ("execute_skill", r"(执行|运行|使用).{0,6}(技能|skill)"),
            ("search_info", r"(最近|查找|搜索|有什么|哪些).*(值得看|进展|更新|论文|资讯|内容|推荐)"),
        ]
        for intent, pattern in rules:
            if re.search(pattern, text, re.IGNORECASE):
                return IntentResult(intent, 0.93, self._entities(intent, text))
        llm_result = self._route_with_llm(text)
        if llm_result:
            return llm_result
        return IntentResult("general_chat", 0.65, {})

    def _entities(self, intent: str, text: str) -> dict[str, Any]:
        entities: dict[str, Any] = {}
        topics = _extract_topics(text)
        if topics:
            entities["topics"] = topics
        if intent == "create_watch":
            entities["source_types"] = _source_types(text)
        if intent in {"create_goal", "save_knowledge"}:
            entities["title"] = _clean_command(text)
        if intent in {"search_info", "query_knowledge", "query_memory"}:
            entities["query"] = text
        return entities

    def _route_with_llm(self, message: str) -> IntentResult | None:
        parsed = llm.chat_json(
            "你是个人秘书的意图路由器。只输出 JSON："
            '{"intent":"...","confidence":0.0,"entities":{}}。'
            f"intent 只能是：{sorted(INTENTS)}。不要回答用户问题。",
            message,
            timeout=20,
        )
        if not parsed or parsed.get("intent") not in INTENTS:
            return None
        return IntentResult(
            str(parsed["intent"]),
            float(parsed.get("confidence") or 0.7),
            parsed.get("entities") if isinstance(parsed.get("entities"), dict) else {},
        )


class ConversationAgent:
    def __init__(self, service: Any) -> None:
        self.service = service
        self.router = IntentRouter()
        self.tools = ToolRegistry(service)

    async def respond(
        self,
        user_id: str,
        message: str,
        history: list[dict[str, Any]],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        routed = self.router.route(message)
        intent = routed.intent
        entities = routed.entities
        actions: list[dict[str, Any]] = []
        memory_updated = False

        if intent == "create_watch":
            topics = entities.get("topics") or _extract_topics(message)
            action = await self.tools.execute("create_watch", user_id, topics=topics)
            actions.append(_public_action(action, topics))
            memory_updated = bool(action.get("result", {}).get("ok"))
            reply = action.get("result", {}).get("note") or "我没有识别出要关注的主题，请再具体说一下。"
            if topics:
                reply += "。后续有重要论文、GitHub 或技术更新时，我会优先纳入推荐。"
        elif intent == "search_info":
            action = await self.tools.execute("search_latest_content", user_id, query=entities.get("query") or message)
            actions.append(_public_action(action))
            reply = _content_reply(action.get("result", {}).get("items") or [], profile)
        elif intent == "change_conversation_setting":
            conversation_profile = self.service.conversation_profile(user_id)
            updated, changed = conversation_profile.update_from_message(message)
            actions.append({"tool": "update_conversation_profile", "status": "success", "summary": "、".join(changed)})
            reply = "已更新对话偏好：" + ("、".join(changed) if changed else "设置已保存") + "。"
            profile = updated
        elif intent == "save_memory":
            topics = entities.get("topics") or _extract_topics(message)
            project = _extract_project(message)
            action = await self.tools.execute("save_memory", user_id, fact=message, topics=topics, project=project)
            actions.append(_public_action(action, topics))
            memory_updated = bool(action.get("result", {}).get("ok"))
            reply = "记住了。" + (f"你最近主要在做 {project}，" if project else "") + (f"重点方向包括 {'、'.join(topics)}。" if topics else "我会把这条作为长期背景使用。")
        elif intent == "query_memory":
            action = await self.tools.execute("search_memory", user_id, query=entities.get("query") or message)
            actions.append(_public_action(action))
            reply = _memory_reply(action.get("result") or {})
        elif intent == "create_goal":
            title = entities.get("title") or _clean_command(message)
            action = await self.tools.execute("create_goal", user_id, title=title)
            actions.append(_public_action(action, [title]))
            reply = f"目标已创建：{title}。我会把它加入后续推荐和提醒的上下文。"
        elif intent == "query_knowledge":
            action = await self.tools.execute("search_knowledge", user_id, query=entities.get("query") or message)
            actions.append(_public_action(action))
            reply = _knowledge_reply(action.get("result", {}).get("items") or [])
        elif intent == "save_knowledge":
            title = entities.get("title") or "对话知识"
            action = await self.tools.execute("save_knowledge", user_id, title=title, content=message)
            actions.append(_public_action(action, [title]))
            reply = f"已保存到个人知识库：{title}。"
        elif intent == "execute_skill":
            action = await self.tools.execute("execute_skill", user_id, skill=(entities.get("skill") or ""))
            actions.append(_public_action(action))
            reply = action.get("result", {}).get("reason") or "当前没有可执行的外部技能。"
        else:
            reply = await self._general_reply(user_id, message, history, profile)

        extracted = await self._extract_memory(user_id, message, intent)
        if extracted:
            actions.append(extracted)
            memory_updated = True
        return {
            "reply": _apply_style(reply, profile),
            "intent": intent,
            "confidence": routed.confidence,
            "entities": entities,
            "actions": actions,
            "memory_updated": memory_updated,
        }

    async def _general_reply(
        self,
        user_id: str,
        message: str,
        history: list[dict[str, Any]],
        profile: dict[str, Any],
    ) -> str:
        memory = await self.tools.execute("get_user_memory", user_id)
        goals = await self.tools.execute("get_goals", user_id)
        context = {
            "conversation_profile": profile,
            "user_memory": memory.get("result", {}).get("memory", {}),
            "relevant_history": history[-8:],
            "current_goals": goals.get("result", {}).get("items", [])[:5],
            "current_message": message,
        }
        generated = llm.chat_text(
            "你是可持续对话的个人办公秘书。结论优先，使用中文，严格依据给定上下文；"
            "不知道时明确说明。不要泄露工具 JSON。",
            json.dumps(context, ensure_ascii=False),
            timeout=35,
        )
        if generated:
            return generated
        name = memory.get("result", {}).get("memory", {}).get("profile", {}).get("display_name") or ""
        return f"{name + '，' if name else ''}我在。你可以直接让我关注主题、查询推荐、记录长期信息或创建目标。"

    async def _extract_memory(self, user_id: str, message: str, intent: str) -> dict[str, Any] | None:
        if intent in {"save_memory", "create_watch"}:
            return None
        stable = re.search(r"(我长期|我通常|我的偏好|我主要做|我最近主要在做|以后请)", message)
        if not stable:
            return None
        topics = _extract_topics(message)
        action = await self.tools.execute(
            "save_memory",
            user_id,
            fact=message,
            topics=topics,
            project=_extract_project(message),
        )
        return _public_action(action, topics)


def _extract_topics(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for topic in KNOWN_TOPICS:
        if topic.lower() in lower and topic not in found:
            found.append(topic)
    match = re.search(r"(?:关注|跟踪|追踪|在做|研究)(.+?)(?:，|。|；|\n|有重要|再告诉|时告诉|$)", text)
    if match:
        segment = match.group(1)
        for part in re.split(r"[、,，/]|\s+和\s+|\s+与\s+", segment):
            topic = re.sub(r"^(一下|最近|主要|有关|关于)", "", part).strip(" ：:的")
            if 2 <= len(topic) <= 30 and topic not in found:
                found.append(topic)
    return found[:8]


def _source_types(text: str) -> list[str]:
    mapping = {"论文": "paper", "GitHub": "github", "博客": "technical_blog", "技术": "technical_blog"}
    rows = [kind for word, kind in mapping.items() if word.lower() in text.lower()]
    return list(dict.fromkeys(rows or ["paper", "github", "technical_blog"]))


def _extract_project(text: str) -> str:
    match = re.search(r"(?:主要在做|主要做|正在做)(.+?)(?:，|。|；|$)", text)
    return match.group(1).strip()[:80] if match else ""


def _clean_command(text: str) -> str:
    return re.sub(r"^(帮我|请|创建|新增|记下|设定|保存|收录|加入)", "", text).strip(" ：:。")[:80]


def _public_action(action: dict[str, Any], labels: list[str] | None = None) -> dict[str, Any]:
    return {
        "tool": action.get("tool") or "",
        "status": action.get("status") or "failed",
        "summary": "、".join(labels or []),
    }


def _content_reply(items: list[dict[str, Any]], profile: dict[str, Any]) -> str:
    if not items:
        return "当前 Radar 里还没有匹配内容。你可以让我先创建关注，下一轮采集后再来看。"
    limit = 5 if profile.get("verbosity") == "detailed" else 3
    lines = ["最近值得看的内容："]
    for index, item in enumerate(items[:limit], 1):
        summary = item.get("summary_zh") or item.get("summary") or ""
        lines.append(f"{index}. {item.get('title')}（相关度 {item.get('score', 0)}%）{('：' + summary) if summary else ''}")
    return "\n".join(lines)


def _memory_reply(result: dict[str, Any]) -> str:
    project = result.get("project") or {}
    topics = project.get("topics") or []
    if project.get("project") or topics:
        return f"你最近主要在做 {project.get('project') or '当前项目'}，重点方向包括 {'、'.join(topics[:8])}。"
    items = result.get("items") or []
    return "我目前记得：" + "；".join(row.get("text", "") for row in items[:6]) if items else "我还没有足够的长期记忆。"


def _knowledge_reply(items: list[dict[str, Any]]) -> str:
    if not items:
        return "个人知识库里暂时没有匹配条目。"
    return "知识库中找到：\n" + "\n".join(f"{i}. {row.get('title')}" for i, row in enumerate(items[:6], 1))


def _apply_style(reply: str, profile: dict[str, Any]) -> str:
    text = (reply or "").strip()
    if profile.get("verbosity") == "concise" and len(text) > 700:
        return text[:700].rstrip() + "…"
    return text
