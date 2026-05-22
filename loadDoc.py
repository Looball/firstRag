import os
from langchain_community.document_loaders import PyMuPDFLoader # PDF解析器
from langchain_community.document_loaders import UnstructuredMarkdownLoader # MD文件加载器
from langchain_text_splitters import RecursiveCharacterTextSplitter # 文本分割器
from langchain_chroma import Chroma # 向量数据库
from typing import List
from langchain_core.embeddings import Embeddings

class ZhipuAIEmbeddings(Embeddings):
    """`Zhipuai Embeddings` embedding models."""
    def __init__(self):
        """
        实例化ZhipuAI为values["client"]

        Args:

            values (Dict): 包含配置信息的字典，必须包含 client 的字段.
        Returns:

            values (Dict): 包含配置信息的字典。如果环境中有zhipuai库，则将返回实例化的ZhipuAI类；否则将报错 'ModuleNotFoundError: No module named 'zhipuai''.
        """
        from zai import ZhipuAiClient
        self.client = ZhipuAiClient(
            api_key=os.environ.get('ZAI_EMD_API')
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        生成输入文本列表的 embedding.
        Args:
            texts (List[str]): 要生成 embedding 的文本列表.

        Returns:
            List[List[float]]: 输入列表中每个文档的 embedding 列表。每个 embedding 都表示为一个浮点值列表。
        """
        batch_size = 64 # 智普AI embedding一次最多接收64条
        all_embeddings = []

        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start:start + batch_size]
            response = self.client.embeddings.create(
                model="embedding-3",
                input=batch_texts
            )
            all_embeddings.extend([item.embedding for item in response.data])

        return all_embeddings


    def embed_query(self, text: str) -> List[float]:
        """
        生成输入文本的 embedding.

        Args:
            texts (str): 要生成 embedding 的文本.

        Return:
            embeddings (List[float]): 输入文本的 embedding，一个浮点数值列表.
        """

        return self.embed_documents([text])[0]


def main():
    # 创建一个 PyMuPDFLoader Class 实例，输入为待加载的 pdf 文档路径
    # loader = PyMuPDFLoader("local_doc/211302010008.pdf")
    # 调用 PyMuPDFLoader Class 的函数 load 对 pdf 文件进行加载
    # pdf_pages = loader.load()
    # print(f"载入后的变量类型为：{type(pdf_pages)}，",  f"该 PDF 一共包含 {len(pdf_pages)} 页")

    # 获取本地文件路径，储存在file_paths里
    file_paths = []
    folder_path = './local_doc'
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_paths.append(file_path)
    print(file_paths[:3])

    # 遍历文件路径并把实例化的loader存放在loaders里
    loaders = []
    for file_path in file_paths:
        file_type = file_path.split('.')[-1]  # 取出文件后缀
        if file_type == 'pdf':
            loaders.append(PyMuPDFLoader(file_path))
        elif file_type == 'md':
            loaders.append(UnstructuredMarkdownLoader(file_path))

    # 下载文件并存储到text
    texts = []

    for loader in loaders:
        texts.extend(loader.load())

    # text = texts[0]
    # print(f"每一个元素的类型：{type(text)}.",
    #     f"该文档的描述性数据：{text.metadata}",
    #     f"查看该文档的内容:\n{text.page_content[0:]}",
    #     sep="\n------\n")

    # 使用langchain_text_splitters的文本分割器
    # 使用递归字符文本分割器
    # 切分文档
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=50)

    split_docs = text_splitter.split_documents(texts)
    print(split_docs)
    print(f"切分后的文件数量：{len(split_docs)}")
    print(f"切分后的字符数（可以用来大致评估 token 数）：{sum([len(doc.page_content) for doc in split_docs])}")

    persist_directory = './vector_db/chroma'

    embedding = ZhipuAIEmbeddings()

    vectordb = Chroma.from_documents(
        documents=split_docs,
        embedding=embedding,
        persist_directory=persist_directory  # 允许我们将persist_directory目录保存到磁盘上
    )

    print(f"向量库中存储的数量：{vectordb._collection.count()}")

    # def save_vector():
    #     vector_store = Chroma(
    #         collection_name="example_collection",
    #         embedding_function=embeddings,
    #         persist_directory="./load/chroma_langchain_db",  # Where to save data locally, remove if not necessary
    #     )


if __name__ == '__main__':
    main()

