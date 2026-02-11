import math
import random

class VectorStore:
    """
    A simple in-memory Vector Database to demonstrate Semantic Joins.
    In production, this connects to Pinecone/Weaviate.
    """
    def __init__(self):
        self.docs = []
        self.vectors = []

    def add_documents(self, documents):
        """
        Simulates embedding documents using an open-source model.
        """
        print("   [VectorStore] Embedding and Indexing documents...")
        for doc in documents:
            self.docs.append(doc)
            # Create a random normalized vector for demo purposes
            # In real life: model.encode(doc['text'])
            vec = [random.random() for _ in range(128)]
            mag = math.sqrt(sum(x*x for x in vec))
            self.vectors.append([x/mag for x in vec])

    def search(self, query, threshold=0.7):
        """
        Performs Cosine Similarity Search (The 'Join' logic).
        """
        # Mock query vector
        q_vec = [random.random() for _ in range(128)]
        q_mag = math.sqrt(sum(x*x for x in q_vec))
        q_vec = [x/q_mag for x in q_vec]

        results = []
        for i, doc_vec in enumerate(self.vectors):
            # Dot product (Cosine Sim)
            score = sum(q * d for q, d in zip(q_vec, doc_vec))
            if score > threshold:
                results.append((self.docs[i], score))
        
        # Sort by relevance
        return sorted(results, key=lambda x: x[1], reverse=True)
