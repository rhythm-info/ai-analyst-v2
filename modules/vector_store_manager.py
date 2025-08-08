# modules/vector_store_manager.py

import streamlit as st
from sqlalchemy import inspect
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings.huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain.tools.retriever import create_retriever_tool

@st.cache_resource
def get_embeddings_model():
    """Initializes and caches the sentence transformer model for creating embeddings."""
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def create_vector_store_retriever(engine, table_names):
    """
    Creates a retriever tool from a vector store containing database schema context.

    This function inspects the database, generates descriptive documents for each
    table and column, and embeds them into a FAISS vector store. This allows the
    agent to perform semantic searches to understand the data's meaning and relationships.

    Args:
        engine: The SQLAlchemy engine connected to the database.
        table_names (list): A list of table names to include in the context.

    Returns:
        A LangChain retriever tool.
    """
    with st.spinner("Building agent's contextual memory..."):
        inspector = inspect(engine)
        documents = []

        for table_name in table_names:
            # Add table-level descriptions
            documents.append(Document(
                page_content=f"Table named '{table_name}' contains data about {table_name.replace('_', ' ')}.",
                metadata={"source": "table_description"}
            ))
            
            # Add column-level descriptions
            columns = inspector.get_columns(table_name)
            for col in columns:
                col_name = col['name']
                col_type = str(col['type'])
                doc_content = (
                    f"The column '{col_name}' in the '{table_name}' table holds "
                    f"{col_name.replace('_', ' ')} information. Its data type is {col_type}."
                )
                
                # Add semantic hints for common ambiguous columns
                if "year" in col_name.lower():
                    doc_content += " This column likely represents a calendar year."
                if "price" in col_name.lower():
                    doc_content += " This is a numerical column representing a monetary value."
                
                documents.append(Document(
                    page_content=doc_content,
                    metadata={"source": "column_description", "table": table_name, "column": col_name}
                ))
        
        # --- Placeholder for user-defined relationships (Future Enhancement) ---
        # In a future version, we can add a UI for users to define joins.
        # For now, we can add example hints if we know the schema.
        # Example:
        # documents.append(Document(
        #     page_content="To join 'cars' and 'owners' tables, use the 'owner_id' column on both.",
        #     metadata={"source": "user_defined_relationship"}
        # ))

        if not documents:
            st.warning("Could not generate any context from the database schema.")
            return None

        embeddings = get_embeddings_model()
        vector_store = FAISS.from_documents(documents=documents, embedding=embeddings)
        
        retriever_tool = create_retriever_tool(
            retriever=vector_store.as_retriever(),
            name="schema_and_relationship_retriever",
            description=(
                "Use this tool FIRST to understand the database schema, table relationships, "
                "or the meaning of columns. It provides context for writing accurate queries."
            )
        )
        st.success("Agent's contextual memory built successfully!")
        return retriever_tool
