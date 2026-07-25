"""
搭建 多agent+RAG资料库 平台

agent可以用不同框架创建: LangChain, langgraph
agent可以用不同架构创建: 单Agent, ReAct, Plan&Excute, Router+Skill, 多agent,
                        Blackboard, Graph/Workflow图工作, AutoGen, CrewAI
agent可根据用户问题自主选择 skill/工具 完成任务

RAG资料库: 本地或云上, 支持文本/图片/视频; 上传可选加载器与分块方法;
检索可启用 Advanced RAG(检索前重写/扩展/分解, 检索中混合+多路召回,
检索后重排/压缩/长上下文重排); agent可自主决定是否调用 RAG

企业级目录结构:
  app/
    main.py            应用工厂
    core/              配置/日志/异常/安全
    api/v1/            路由层
    schemas/           Pydantic 模型
    services/          业务逻辑
    models/            ORM 模型
    db/                数据库连接
    utils/             工具
  main.py              启动入口 (本文件)
"""
import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
