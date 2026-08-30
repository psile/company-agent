"""Intent routing and tool-based planning for the personal secretary agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from . import llm
from .agent_tools import ToolRegistry
from .skills.project_tracker import ProjectTrackerSkill
from .skills.reminder import ReminderSkill
from .skills.report import ReportSkill, infer_report_type
from .skills.task_capture import TaskCaptureSkill


INTENTS = {
    "general_chat",
    "search_info",
    "create_watch",
    "update_watch",
    "create_goal",
    "update_goal",
    "create_task",
    "create_reminder",
    "generate_report",
    "query_project",
    "update_task",
    "breakdown_task",
    "save_note",
    "search_memory",
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


TASK_HINT = re.compile(
    r"(关注|跟踪|追踪|盯住|目标|计划|记住|记下|知识库|推荐|论文|搜索|查找|技能|偏好|简洁|详细|少推送|少打扰|周五|明天|待办|提醒我|做完|拆|工作重点|日报|周报|工作总结|项目到哪|进展怎么样)"
)


class IntentRouter:
    def route(self, message: str) -> IntentResult:
        text = (message or "").strip()
        rules = [
            ("change_conversation_setting", r"(以后|回答|回复|技术问题|普通问题).*(简洁|简短|详细|结论|先问|确认|主动|少推送|少打扰)"),
            ("generate_report", r"(生成|写|出一份?).{0,8}(今日|今天|本日)?(日报|工作总结)"),
            ("generate_report", r"(生成|写).{0,8}(本周|这周|周报|一周总结)"),
            ("generate_report", r"(生成本周总结|本周工作总结|本周总结)"),
            ("generate_report", r"(月度总结|项目总结|一键生成.{0,6}(日报|周报))"),
            ("query_project", r"(这个)?项目(现在)?(进展|进度)?怎么样"),
            ("query_project", r"(项目).{0,20}(到哪了|进展如何|进度如何|现在怎样)"),
            ("query_project", r"(我的).{0,40}(项目|Personal Agent|World Model).{0,16}(到哪了|进展|怎么样)"),
            ("breakdown_task", r"(拆|拆解|拆一下).{0,12}(任务|待办|这个|一下)?"),
            ("create_reminder", r"(生成|给我|看看).{0,8}(今日|今天).{0,8}(工作重点|提醒)"),
            ("create_reminder", r"(今日|今天)工作重点"),
            ("create_reminder", r"(明天|后天|今晚|今天下午).{0,16}提醒我"),
            ("create_reminder", r"提醒我.{0,40}(明天|后天|下午|上午|今晚|\d{1,2}点|[一二三四五六七八九十两]点)"),
            ("create_reminder", r"(等下|待会|一会儿|一会|\d{1,2}点|[一二三四五六七八九十两]点).{0,48}提醒我"),
            ("create_task", r"(周五|星期[一二三四五六日天]|周[一二三四五六日]|明天|后天|这周|本周|下周).{0,24}(完成|做完|整理|准备|发|写|验证|做)"),
            ("create_task", r"提醒我"),
            ("create_task", r"(记一下|帮我记|记下).{0,30}(要|完成|做|验证|发|准备|整理)"),
            ("update_task", r"(完成了|标记完成|开始做).{0,8}(任务|待办)?"),
            ("save_note", r"(记一下|帮我记|记下).{0,30}(要|完成|做|验证|发|准备|整理)"),
            ("search_memory", r"(你记得|还记得|我最近主要(研究|在做)什么|我在研究什么|我主要研究什么|最近在研究)"),
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
        # Casual chat should not pay a second model round-trip just to classify intent.
        if not TASK_HINT.search(text):
            return IntentResult("general_chat", 0.8, {})
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
        if intent in {"search_info", "query_knowledge", "query_memory", "search_memory"}:
            entities["query"] = text
        if intent == "generate_report":
            entities["report_type"] = infer_report_type(text)
        return entities

    def _route_with_llm(self, message: str) -> IntentResult | None:
        parsed = llm.chat_json(
            "你是个人秘书的意图路由器。只输出 JSON："
            '{"intent":"...","confidence":0.0,"entities":{}}。'
            f"intent 只能是：{sorted(INTENTS)}。不要回答用户问题。",
            message,
            timeout=12,
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
        elif intent in {"query_memory", "search_memory"}:
            action = await self.tools.execute("search_memory", user_id, query=entities.get("query") or message)
            actions.append(_public_action(action))
            reply = _memory_reply(action.get("result") or {})
        elif intent == "create_goal":
            title = entities.get("title") or _clean_command(message)
            action = await self.tools.execute("create_goal", user_id, title=title)
            actions.append(_public_action(action, [title]))
            reply = f"目标已创建：{title}。我会把它加入后续推荐和提醒的上下文。"
        elif intent == "generate_report":
            captured = await ReportSkill(self.service).execute(
                user_id,
                {"message": message, "report_type": entities.get("report_type") or infer_report_type(message)},
            )
            row = captured.get("report") or {}
            reply = captured.get("reply") or "已生成工作总结。"
            actions.append(
                {
                    "tool": "report",
                    "status": "success" if captured.get("ok") else "failed",
                    "summary": row.get("title") or entities.get("report_type") or "日报",
                }
            )
            memory_updated = bool(row)
        elif intent == "query_project":
            captured = await ProjectTrackerSkill(self.service).execute(user_id, {"message": message})
            reply = captured.get("reply") or "暂时还没有足够的项目上下文。"
            actions.append(
                {
                    "tool": "project_tracker",
                    "status": "success" if captured.get("ok") else "failed",
                    "summary": (captured.get("tracker") or {}).get("project") or "当前项目",
                }
            )
        elif intent == "create_reminder":
            captured = await ReminderSkill(self.service).execute(user_id, {"message": message})
            created = captured.get("created") or []
            reply = captured.get("reply") or "已记下提醒。"
            actions.append(
                {
                    "tool": "reminder",
                    "status": "success" if captured.get("ok") else "failed",
                    "summary": (captured.get("reminder") or {}).get("reminder_type")
                    or ("工作重点" if captured.get("fired") else "提醒"),
                }
            )
            memory_updated = bool(created or captured.get("reminder") or captured.get("fired"))
        elif intent == "create_task":
            captured = await TaskCaptureSkill(self.service).execute(user_id, {"message": message})
            created = captured.get("created") or []
            if captured.get("reply"):
                reply = captured["reply"]
                actions.append(
                    {
                        "tool": "task_capture",
                        "status": "success" if created or captured.get("pending") or captured.get("note") else "skipped",
                        "summary": "、".join(row.get("title") or "" for row in created) or (captured.get("reply") or "")[:40],
                    }
                )
                memory_updated = bool(created or captured.get("note"))
            else:
                reply = await self._general_reply(user_id, message, history, profile)
        elif intent == "breakdown_task":
            captured = await TaskCaptureSkill(self.service).breakdown(user_id, None, message)
            created = captured.get("created") or []
            reply = captured.get("reply") or "暂时无法拆解。"
            actions.append({"tool": "task_breakdown", "status": "success" if created else "failed", "summary": f"{len(created)} 个子任务"})
            memory_updated = bool(created)
        elif intent == "update_task":
            open_tasks = self.service.list_tasks(user_id, include_done=False)
            if open_tasks and re.search(r"完成", message):
                updated = self.service.update_task(open_tasks[0]["id"], {"status": "done"}, user_id=user_id)
                reply = f"已把「{updated['title']}」标为完成。"
                actions.append({"tool": "update_task", "status": "success", "summary": updated["title"]})
                memory_updated = True
            else:
                reply = "没有找到可更新的待办。你也可以在「我的工作」里直接点完成。"
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
        scope = self.service.for_user(user_id)
        mem = scope.user_memory.context()
        goals = scope.workspace.goals()[:5]
        from .retrieve import public_hits, retrieve

        recalled = public_hits(retrieve(scope, message, limit=6))
        context = _compact_chat_context(mem, goals, history, profile, message, recalled)
        generated = llm.chat_text(
            "你是可持续对话的个人办公秘书。用中文，结论优先，2–4 句即可。"
            "用户没问目标或推荐时不要主动罗列进度。不要泄露工具 JSON。",
            json.dumps(context, ensure_ascii=False),
            timeout=25,
            max_tokens=350,
        )
        if generated:
            return generated
        name = (mem.get("profile") or {}).get("display_name") or ""
        return _fallback_general_reply(name, message)

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


def _compact_chat_context(
    memory: dict[str, Any],
    goals: list[dict[str, Any]],
    history: list[dict[str, Any]],
    profile: dict[str, Any],
    message: str,
    recalled: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    person = memory.get("profile") or {}
    project = memory.get("project") or {}
    interests = [str(row.get("topic") or "") for row in (memory.get("interests") or [])[:6] if row.get("topic")]
    return {
        "name": person.get("display_name") or "",
        "role": person.get("role") or "",
        "project": project.get("project") or "",
        "interests": interests[:4],
        "recalled": recalled or [],
        "goals": [
            {"title": row.get("title"), "progress": row.get("progress")}
            for row in goals[:4]
            if row.get("title")
        ],
        "style": {
            "verbosity": profile.get("verbosity") or "concise",
            "technical_detail": profile.get("technical_detail") or "",
        },
        "history": [
            {"role": row.get("role"), "content": str(row.get("content") or "")[:180]}
            for row in history[-6:]
        ],
        "message": message,
    }


def _fallback_general_reply(name: str, message: str) -> str:
    """Distinct replies when the model is unavailable. Avoid a single canned line."""
    prefix = f"{name}，" if name else ""
    text = (message or "").strip()
    if re.search(r"^(你好|您好|hi+|hello|hey|在吗|早上好|晚上好)[!！。.?？]*$", text, re.I):
        return f"{prefix}我在。你可以直接让我关注主题、查询推荐、记录长期信息或创建目标。"
    if re.search(r"(你是谁|你叫什么|介绍一下你|你是什么)", text):
        return (
            f"{prefix}我是你的个人工作秘书。"
            "我会记住你的兴趣和项目，观察外部信息，并在合适的时候推送或回答。"
        )
    if re.search(r"(能做什么|帮我做什么|你会什么|有什么能力|可以做什么)", text):
        return (
            "我可以帮你持续关注主题、查最近值得看的内容、记下长期偏好和目标、查询知识库。"
            "直接用一句话说想做什么即可，例如「最近帮我关注 World Model」。"
        )
    if re.search(r"(记录|记下|记住).*(吗|么|呢|不)", text) or re.search(r"^(能|可以)记", text):
        return "可以。直接说「记住……」或「我最近主要在做……」，我会写入长期记忆，之后问我时还能用上。"
    return (
        f"{prefix}当前模型暂时不可用，我还不能自由闲聊。"
        "你可以让我关注主题、查询推荐、记录长期信息或创建目标。"
    )


def _apply_style(reply: str, profile: dict[str, Any]) -> str:
    text = (reply or "").strip()
    if profile.get("verbosity") == "concise" and len(text) > 700:
        return text[:700].rstrip() + "…"
    return text
