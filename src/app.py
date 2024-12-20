import streamlit as st
import os
import requests
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.messages import AIMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()
# Create a directory to persist the Chroma database
CHROMA_PATH = "chroma_db"
os.makedirs(CHROMA_PATH, exist_ok=True)


def get_vectorstore_from_url(url):
    # Create a directory to persist the Chroma database
    CHROMA_PATH = "chroma_db"
    os.makedirs(CHROMA_PATH, exist_ok=True)

    # get text and convert to document
    response = requests.get("https://r.jina.ai/" + url)
    document = Document(page_content=response.text, metadata={"source": url})

    # split the document into chunks
    text_splitter = RecursiveCharacterTextSplitter()
    document_chunks = text_splitter.split_documents([document])

    # create a vectorstore from chunks with persistent storage
    vector_store = Chroma.from_documents(
        document_chunks, OpenAIEmbeddings(), persist_directory=CHROMA_PATH
    )

    return vector_store


def get_context_retriever_chain(vector_store):
    llm = ChatOpenAI()

    retriever = vector_store.as_retriever()

    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            (
                "user",
                "Given the above conversation, generate a search query to look up in order to get information relevant to the conversation",
            ),
        ]
    )

    retriever_chain = create_history_aware_retriever(llm, retriever, prompt)

    return retriever_chain


def get_conversational_rag_chain(retriever_chain):
    llm = ChatOpenAI()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer the user's questions based on the below context:\n\n{context}",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ]
    )

    stuff_documents_chain = create_stuff_documents_chain(llm, prompt)

    return create_retrieval_chain(retriever_chain, stuff_documents_chain)


def get_response(user_input):
    retriever_chain = get_context_retriever_chain(st.session_state.vector_store)
    conversation_rag_chain = get_conversational_rag_chain(retriever_chain)

    response = conversation_rag_chain.invoke(
        {"chat_history": st.session_state.chat_history, "input": user_input}
    )

    return response["answer"]


# app config
st.set_page_config(page_title="Chat with websites", page_icon="🤖")
st.title("Chat with websites")

# sidebar
with st.sidebar:
    st.header("Settings")
    website_url = st.text_input("Website URL")

if website_url is None or website_url == "":
    st.info("Please enter a website URL")

else:
    # session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            AIMessage(content="Hello, I am a bot. How can I help you?"),
        ]
    if "vector_store" not in st.session_state:
        try:
            # Attempt to load an existing vector store with a persistent path
            st.session_state.vector_store = Chroma(
                persist_directory=CHROMA_PATH, embedding_function=OpenAIEmbeddings()
            )

            # Check if the vector store is empty
            if st.session_state.vector_store._collection.count() == 0:
                # Create a new vector store if the existing one is empty
                st.session_state.vector_store = get_vectorstore_from_url(website_url)
        except Exception as e:
            st.error(f"Error loading vector store: {e}")
            # Create a new vector store
            st.session_state.vector_store = get_vectorstore_from_url(website_url)

    # user input
    user_query = st.chat_input("Type your message here...")
    if user_query is not None and user_query != "":
        response = get_response(user_query)
        st.session_state.chat_history.append(HumanMessage(content=user_query))
        st.session_state.chat_history.append(AIMessage(content=response))

    # conversation
    for message in st.session_state.chat_history:
        if isinstance(message, AIMessage):
            with st.chat_message("AI"):
                st.write(message.content)
        elif isinstance(message, HumanMessage):
            with st.chat_message("Human"):
                st.write(message.content)
                st.write(message.content)
