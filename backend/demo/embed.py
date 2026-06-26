import os
from zai import ZhipuAiClient

def zhipu_embedding(text: str):
    client = ZhipuAiClient(
        api_key=os.environ.get('ZAI_EMD_API')
    )
    
    response = client.embeddings.create(
        model="embedding-3", #填写需要调用的模型编码
        input=text,
    )
    return response


def main():
    text = '要生成 embedding 的输入文本，字符串形式。'
    response = zhipu_embedding(text=text)
    print(f'response类型为：{type(response)}')
    print(f'embedding类型为：{response.object}')
    print(f'生成embedding的model为：{response.model}')
    print(f'生成的embedding长度为：{len(response.data[0].embedding)}')
    print(f'embedding（前10）为: {response.data[0].embedding[:10]}')



if __name__ == '__main__':
    main()


