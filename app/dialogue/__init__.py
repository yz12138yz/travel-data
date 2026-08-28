"""旅游智能客服 —— 对话系统核心包。

仿照「电商小二」项目的分层结构实现，面向旅游行业：
    - 信息检索（产品咨询 / 订单查询 / 出行信息 / 政策咨询）
    - 任务型对话（订单查询 / 出行信息 / 退款申请 / 工单提交）
    - 对话管控（槽位收集 / 上下文保持 / 流程切换·恢复·取消）
    - 闲聊兜底 / 意图澄清
    - 对话状态持久化与可观测性

包结构（与电商小二一一对应）：

- ``state``          -> DialogueState 设计与定义
- ``state_repository`` -> 对话状态持久化仓库（DialogueStateRepository）
- ``intent``         -> 意图定义与规则识别器（可插拔）
- ``planning``       -> Planning 模块（意图规划 + 槽位规划）
- ``responder``      -> ClarifyResponder（意图澄清）
- ``handlers``       -> TaskHandler / KnowledgeHandler / ChitchatHandler
- ``actions``        -> 自定义 Action（业务查询，对接 travel 数据库）
- ``engine``         -> DialogueEngine（编排）
- ``service``        -> DialogueService（会话入口）
- ``router``         -> FastAPI 接口
"""

__all__ = [
    "state",
    "state_repository",
    "intent",
    "planning",
    "responder",
    "engine",
    "service",
    "router",
]
