# 导入langchain官方deepseek包
from langchain_core.tools import retriever
from langchain_deepseek import ChatDeepSeek

# 导入os模块获取环境变量 $DEEPSEEK_API_KEY
import os

# 导入聊天模版，更加灵活的组织prompt
from langchain_core.prompts import ChatPromptTemplate,PromptTemplate

# 导入RunnablePassthrough, RunnableParallel 并行导入提示词模版
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
# 导入链条 选择分支
from langchain_core.runnables import RunnableBranch

# 导入langchain 输出解析器
from langchain_core.output_parsers import StrOutputParser
# 创建 输出解析器
output_parser = StrOutputParser()

# 导入embedding模型
from loadDoc import ZhipuAIEmbeddings
# 创建文本嵌入对象
embedding = ZhipuAIEmbeddings()

# 导入 向量数据库 包
from langchain_chroma import Chroma # 向量数据库
# 指定向量数据库目录
persist_directory = './vector_db/chroma'
# 加载数据库
vectordb = Chroma(
    persist_directory=persist_directory,  # 允许我们将persist_directory目录保存到磁盘上
    embedding_function=embedding
)

# 导入RunnableLambda，用来自定义LCEL
from langchain_core.runnables import RunnableLambda



# 创建 LLM 模型
model = ChatDeepSeek(
    model="deepseek-v4-flash",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key= os.environ.get('DEEPSEEK_API_KEY'),
    # other params...
)

# 组织提示词
# template = "你是一个翻译助手，可以帮助我将 {input_language} 翻译成 {output_language}."
# human_template = "{text}"
#
# chat_prompt = ChatPromptTemplate([
#     ("system", template),
#     ("human", human_template),
# ])
#
# text = "我带着比身体重的行李，\
# 游入尼罗河底，\
# 经过几道闪电 看到一堆光圈，\
# 不确定是不是这里。\
# "
#
# messages  = chat_prompt.invoke({"input_language": "中文", "output_language": "英文", "text": text})


# # 调用 LLM 模型
# output = model.invoke(messages)
# print(output)
# print(output.text)
#
# # 格式化输出
# output_parser = StrOutputParser()
# test = output_parser.invoke(output)
# print(test)

# 创建问答链 提示词 -> 模型 -> 输出
# chain = chat_prompt | model | output_parser
# a = chain.invoke({"input_language":"中文", "output_language":"日文","text": text})
# print(a)

# 对问题进行向量检索，返回本地知识库中最相关的context
# question = '模型微调的一般流程是什么'
# res_vect = vectordb.as_retriever(search_type='similarity',search_kwargs={"k": 2})
# docs = res_vect.invoke(question)
# print(f"检索到的内容数：{len(docs)}")
#
#
# for i, doc in enumerate(docs):
#     print(f"检索到的第{i+1}个内容: \n {doc.page_content}", end="\n-----------------------------------------------------\n")


# 创建LCEL，组建 问题向量检索链
# print('-'*50)
# res_vect = vectordb.as_retriever(search_type='similarity',search_kwargs={"k": 2})
# combiner = RunnableLambda(combine_docs)
# retrieval_chain = res_vect | combiner
# res = retrieval_chain.invoke("模型微调的一般流程是什么")
# print(res)


# 组织检索+问答链，构建检索后的 ->提示词 -> 模型调用 -> 输出 链条
# template = """使用以下上下文来回答最后的问题。如果你不知道答案，就说你不知道，不要试图编造答
# 案。最多使用三句话。尽量使答案简明扼要。请你在回答的最后说“谢谢你的提问！”。
# {context}
# 问题: {input}"""

# template = """你是一个问答助手。请优先依据【知识库上下文】回答问题。
# 如果知识库上下文不足，可以结合你的通用知识进行补充，但要明确区分来源。
#
# 【知识库上下文】
# {context}
#
# 问题: {input}
#
# 请按以下格式回答：
# 【知识库依据】
# ...
#
# 【模型补充】
# ...
# """

# 将template通过 PromptTemplate 转为可以在LCEL中使用的类型
# prompt = PromptTemplate(template=template)
#
# qa_chain = (
#     RunnableParallel({"context": retrieval_chain, "input": RunnablePassthrough()})
#     | prompt
#     | model
#     | StrOutputParser()
# )

# question_1 = "什么是模型微调？"
# question_2 = "模型微调的一般流程是什么"
#
# result = qa_chain.invoke(question_1)
# print("大模型+知识库后回答 question_1 的结果：")
# print(result)
#
# result = qa_chain.invoke(question_2)
# print("大模型+知识库后回答 question_2 的结果：")
# print(result)



# 问答链的系统prompt
system_prompt = (
    "你是一个问答任务的助手。 "
    "请使用检索到的上下文片段回答这个问题。 "
    "如果你不知道答案就说不知道。 "
    "请使用简洁的话语回答用户。"
    "\n\n"
    "{context}"
)
# 制定prompt template
qa_prompt = ChatPromptTemplate(
    [
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ]
)


# 压缩问题的系统 prompt
condense_question_system_template = (
    "请根据聊天记录完善用户最新的问题，"
    "如果用户最新的问题不需要完善则返回用户的问题。"
    )

# 构造 压缩问题的 prompt template
condense_question_prompt = ChatPromptTemplate([
        ("system", condense_question_system_template),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ])

# 构造检索文档的链
res_vect = vectordb.as_retriever(search_type='similarity',search_kwargs={"k": 2})

# RunnableBranch 会根据条件选择要运行的分支
retrieve_docs = RunnableBranch(
    # 分支 1: 若聊天记录中没有 chat_history 则直接使用用户问题查询向量数据库
    (lambda x: not x.get("chat_history", False), (lambda x: x["input"]) | res_vect, ),
    # 分支 2 : 若聊天记录中有 chat_history 则先让 llm 根据聊天记录完善问题再查询向量数据库
    condense_question_prompt | model | StrOutputParser() | res_vect,
)

def combine_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs['context'])

# 定义问答链
qa_chain = (
    RunnablePassthrough.assign(context=combine_docs) # 使用 combine_docs 函数整合 qa_prompt 中的 context
    | qa_prompt # 问答模板
    | model
    | StrOutputParser() # 规定输出的格式为 str
)

# 定义带有历史记录的问答链
qa_history_chain = RunnablePassthrough.assign(
    context = (lambda x: x) | retrieve_docs # 将查询结果存为 content
    ).assign(answer=qa_chain) # 将最终结果存为 answer

# # 不带聊天记录
# _ = qa_history_chain.invoke({
#     "input": "什么是预训练模型微调",
#     "chat_history": []
# })
# print(_['answer'])


# 带聊天记录  理想
__ = qa_history_chain.invoke({
    "input": "它的一般流程是什么",
    "chat_history": [
        ("human", "什么是预训练模型微调"),
        ("ai", "预训练模型微调是指在已预训练好的模型（如BERT）基础上，针对具体下游任务（如分类、问答）对模型参数进行进一步训练的过程。\
        其核心是复用预训练学到的通用语言知识，仅调整少量任务相关参数（或全部参数），\
        从而在少量标注数据上高效适应新任务。常见策略包括全参微调、参数高效微调（如LoRA）和提示调优"),
    ]
})
print(__['answer'])

# 不理想
__ = qa_history_chain.invoke({
    "input": "它的技术流程是什么",
    "chat_history": [
        ("human", "什么是预训练模型微调"),
        ("ai", "预训练模型微调是指在已预训练好的模型（如BERT）基础上，针对具体下游任务（如分类、问答）对模型参数进行进一步训练的过程。\
        其核心是复用预训练学到的通用语言知识，仅调整少量任务相关参数（或全部参数），\
        从而在少量标注数据上高效适应新任务。常见策略包括全参微调、参数高效微调（如LoRA）和提示调优"),
    ]
})
print(__['answer'])


