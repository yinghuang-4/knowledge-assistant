import chromadb
from openai import OpenAI
import os
client = OpenAI(api_key=os.environ.get('ZHIPU_API_KEY'),base_url="https://open.bigmodel.cn/api/paas/v4")
#检索函数
def embed(text):
    response = client.embeddings.create(
        model="embedding-3",
        input=text
    )
    return response.data[0].embedding 
#读取文件
with open("notes.txt", "r",encoding="utf-8") as f:
    text = f.read()
chunks = [chunk for chunk in text.split("\n") if chunk.strip()]
#将段落嵌入
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="kb_notes")
collection.add(
    ids=[str(i) for i in range(len(chunks))], 
    documents=chunks,
    embeddings=[embed(chunk) for chunk in chunks],
    metadatas=[{"notes_index": i} for i in range(len(chunks))],
)
print(collection.count())