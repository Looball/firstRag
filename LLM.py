# 导入langchain官方deepseek包
from langchain_core.tools import retriever
from langchain_deepseek import ChatDeepSeek

# 导入os模块获取环境变量 $DEEPSEEK_API_KEY
import os

# 导入聊天模版，更加灵活的组织prompt
from langchain_core.prompts import ChatPromptTemplate

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
def combine_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


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
template = "你是一个翻译助手，可以帮助我将 {input_language} 翻译成 {output_language}."
human_template = "{text}"

chat_prompt = ChatPromptTemplate([
    ("system", template),
    ("human", human_template),
])

text = "我带着比身体重的行李，\
游入尼罗河底，\
经过几道闪电 看到一堆光圈，\
不确定是不是这里。\
"

messages  = chat_prompt.invoke({"input_language": "中文", "output_language": "英文", "text": text})


# # 调用 LLM 模型
# output = model.invoke(messages)
# print(output)
# print(output.text)
#
# # 格式化输出
# output_parser = StrOutputParser()
# test = output_parser.invoke(output)
# print(test)

# 创建组合链
chain = chat_prompt | model | output_parser
a = chain.invoke({"input_language":"中文", "output_language":"日文","text": text})
print(a)

# 对问题进行向量检索，返回本地知识库中最相关的context
question = '模型微调的一般流程是什么'
res_vect = vectordb.as_retriever(search_type='similarity',search_kwargs={"k": 2})
docs = res_vect.invoke(question)
print(f"检索到的内容数：{len(docs)}")


for i, doc in enumerate(docs):
    print(f"检索到的第{i+1}个内容: \n {doc.page_content}", end="\n-----------------------------------------------------\n")


# 创建LCEL，组建 问题向量检索链
print('------------------------------')
combiner = RunnableLambda(combine_docs)
retrieval_chain = res_vect | combiner
res = retrieval_chain.invoke("模型微调的一般流程是什么")
print(res)




