import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

class DevOpsMemory:
    def __init__(self):
        self.persist_directory = os.getenv("CHROMA_PATH", "./chroma_data")
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Using a local embedding function suitable for CPU
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        self.collection = self.client.get_or_create_collection(
            name="devops_history",
            embedding_function=self.embedding_fn
        )

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
