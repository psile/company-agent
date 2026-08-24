# 工位萌宠秘书 · W0

专属办公秘书的第一周内核。品类是秘书，不是更弱的飞书 aily，也不是办公版 EchoBot。

对外三个词：**专属、少扰、能记。**  
本周只做：**设周/日目标 → 勾完成 → 预览确认后成卡 → 满条件升到 Lv2。**

## 硬约束（写进代码，不是文档愿望）

- 周目标最多 3，日目标最多 3
- 工作日主动推送：上班 1 + 下班 1；兴趣 0–1；深度工作禁止弹窗
- 未完成、未确认、无 `source_url`，不准入库
- 升级不跳级：Lv3 才开关注源，Lv5 才开群提醒
- 明确不做：写 PPT、虚拟电脑、管项目、群监听、自动建库、陪聊推送

## 包结构

| 模块 | 职责 |
|---|---|
| `secretary.goals` | 周/日目标与完成事件 |
| `secretary.quota` | 打扰预算 |
| `secretary.filing` | 完成即归档（预览确认） |
| `secretary.levels` | Lv1–Lv5 能力门闩 |
| `secretary.non_goals` | 冻结的「不做」清单 |

EchoBot 只当后续 pet runtime 依赖，不在 `EchoBot-main` 里改办公逻辑。飞书通道是下一刀，本包先把规则测绿。

## 运行测试

```shell
python -m pytest secretary/tests -q
```
