"""Office Skills catalog for the workbench. Not per-user data."""

from __future__ import annotations

from typing import Any


OFFICE_SKILLS: list[dict[str, Any]] = [
    {
        "id": "task_capture",
        "name": "Task Capture",
        "title": "任务捕捉",
        "summary": "自动识别工作事项",
        "status": "enabled",
        "href": "#/chat",
        "example": "周五前把 Personal Agent PPT 做完，提醒我。",
    },
    {
        "id": "task_planner",
        "name": "Task Planner",
        "title": "任务规划",
        "summary": "任务拆解与规划",
        "status": "enabled",
        "href": "#/work",
        "example": "帮我拆一下这个任务。",
    },
    {
        "id": "work_brief",
        "name": "Work Brief",
        "title": "今日重点",
        "summary": "每日工作重点",
        "status": "enabled",
        "href": "#/chat",
        "example": "给我今天的工作重点。",
    },
    {
        "id": "reminder",
        "name": "Smart Reminder",
        "title": "智能提醒",
        "summary": "结合任务与进度主动提醒",
        "status": "enabled",
        "href": "#/work",
        "example": "明天下午提醒我发方案给老板。",
    },
    {
        "id": "daily_report",
        "name": "Daily Report",
        "title": "日报生成",
        "summary": "根据 Task 和事件汇总今日工作",
        "status": "enabled",
        "href": "#/reports",
        "report_type": "daily",
    },
    {
        "id": "weekly_report",
        "name": "Weekly Report",
        "title": "周报生成",
        "summary": "根据一周工作记忆生成周报",
        "status": "enabled",
        "href": "#/reports",
        "report_type": "weekly",
    },
    {
        "id": "project_tracker",
        "name": "Project Tracker",
        "title": "项目跟踪",
        "summary": "估算项目进度并给出下一步",
        "status": "enabled",
        "href": "#/projects",
        "example": "这个项目现在进展怎么样？",
    },
    {
        "id": "research",
        "name": "Research Assistant",
        "title": "研究助手",
        "summary": "技术资料研究",
        "status": "coming_soon",
    },
    {
        "id": "knowledge_organizer",
        "name": "Knowledge Organizer",
        "title": "知识整理",
        "summary": "资料自动整理",
        "status": "coming_soon",
    },
    {
        "id": "meeting",
        "name": "Meeting Assistant",
        "title": "会议助手",
        "summary": "纪要提取任务与决策",
        "status": "coming_soon",
    },
    {
        "id": "decision",
        "name": "Decision Memory",
        "title": "决策记忆",
        "summary": "记住为什么当时那样决定",
        "status": "coming_soon",
    },
    {
        "id": "deliverable",
        "name": "Deliverable Generator",
        "title": "交付物生成",
        "summary": "汇报提纲与工作材料",
        "status": "coming_soon",
    },
]


def list_office_skills() -> list[dict[str, Any]]:
    return [dict(row) for row in OFFICE_SKILLS]
