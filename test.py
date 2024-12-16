from langchain_core.documents import Document
import requests

url = "https://www.uchicago.edu/"

response = requests.get("https://r.jina.ai/" + url)
document = Document(page_content=response.text, metadata={"source": url})

print(document)
