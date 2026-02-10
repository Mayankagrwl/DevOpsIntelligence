import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

class DevOpsMemory:
    def __init__(self):
        self.persist_directory = os.getenv("CHROMA_PATH", "./chroma_data")
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Use local Ollama for embeddings to avoid external DNS issues
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        # Ensure we point to the /api endpoint if the library requires it, 
        # but usually the base URL is enough for the OllamaEmbeddingFunction
        self.embedding_fn = embedding_functions.OllamaEmbeddingFunction(
            url=f"{ollama_url}/api/embeddings",
            model_name=os.getenv("OLLAMA_EMBED_MODEL", "llama3.1")
        )
        
        # Handle collection creation with conflict resolution
        # If the embedding function changes (e.g. default -> ollama), Chroma throws a ValueError
        try:
            self.collection = self.client.get_or_create_collection(
                name="devops_history",
                embedding_function=self.embedding_fn
            )
        except ValueError as e:
            if "Embedding function conflict" in str(e):
                # If there's a conflict, the old data is incompatible anyway.
                # Recreate the collection with the new local embedding model.
                self.client.delete_collection("devops_history")
                self.collection = self.client.create_collection(
                    name="devops_history",
                    embedding_function=self.embedding_fn
                )
            else:
                raise e

    def store_interaction(self, query, resolution):
        """Stores a resolved interaction in memory."""
        # Use a combination of query and resolution for the passage
        content = f"Question: {query}\nResolution: {resolution}"
        
        # Simple ID generation
        import uuid
        doc_id = str(uuid.uuid4())
        
        self.collection.add(
            documents=[content],
            ids=[doc_id],
            metadatas=[{"type": "resolution"}]
        )

    def retrieve_context(self, query, n_results=3):
        """Retrieves relevant past interactions based on similarity."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if not results['documents'] or not results['documents'][0]:
            return ""
        
        context = "\n---\n".join(results['documents'][0])
        return f"\nRelevant past context:\n{context}\n"

    def check_memory_status(self):
        """Verify memory is accessible."""
        try:
            self.client.heartbeat()
            return True
        except:
            return False
