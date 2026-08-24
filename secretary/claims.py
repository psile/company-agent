"""产品主张与硬边界。W0 代码和试点话术共用这一份，避免各写各的。"""

from __future__ import annotations

POSITIONING = {
    "product_name": "工位萌宠秘书",
    "internal_name": "秘书",
    "forbidden_external_name": "EchoBot",
    "category": "专属办公秘书",
    "one_liner": (
        "工位上的专属萌宠秘书：按你的目标和作息守着；飞书里帮你收口；"
        "你勾完成之后，把当天相关文档收成可回看的私人卡片。"
        "越用越像你的人，而不是越用越吵。"
    ),
    "headline_words": ("专属", "少扰", "能记"),
    "form_words": ("萌宠", "飞书"),
    "mechanism_words": ("完成即归档", "升级即解锁"),
    "vs_aily": "他们帮你做新的；我们帮你守节奏、记住你做完的。",
}

# capability_id → 用户问起时的回复
NON_GOALS: dict[str, str] = {
    "aily_ppt": "这类请用飞书 aily；我只在你勾完成后整理。",
    "virtual_computer": "这类请用飞书 aily；我不做虚拟电脑或浏览器代操作。",
    "project_management": "周目标最多 3、日目标最多 3。完成是为了归档，不是管项目。",
    "group_listen": "群提醒还没开。开了也只走白名单和官方 API。",
    "auto_library": "没勾完成、你没点确认，我不会入库。",
    "client_hook": "只走官方飞书 Bot API，不做客户端 hook。",
    "chit_chat": "工位上我可以可爱地坐着，但不陪聊。",
    "public_cloud_docs": "内部文档不送公网模型。",
}


def refuse(capability_id: str) -> str:
    """返回锁定不做的标准回复。未知能力一律拒绝扩展范围。"""
    if capability_id in NON_GOALS:
        return NON_GOALS[capability_id]
    return "这超出我现在的范围。W0 只做目标、完成和归档。"
