"""
MIMIC Support Bot - RAG (Retrieval-Augmented Generation) Engine

This module implements an AI-powered support bot using:
- OpenAI GPT-4o-mini for chat completions
- OpenAI text-embedding-3-small for embeddings
- pgvector (PostgreSQL) or in-memory fallback for vector storage
- LangChain for the RAG pipeline

Features:
- Answers questions based on documentation (README, DEV_MANUAL, FAQ)
- Confidence scoring for responses
- Automatic ticket creation for low-confidence answers
- Conversation history for context
- Integration with web chat and Telegram

Usage:
    from support_bot import SupportBot
    
    bot = SupportBot()
    response = bot.chat("How do I connect my Binance account?", session_id="abc123")
"""

import os
import json
import logging
import hashlib
import secrets
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

logger = logging.getLogger("SupportBot")

# Try to import OpenAI and LangChain
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI not installed. Install with: pip install openai")

try:
    from langchain_openai import OpenAIEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("⚠️ LangChain not installed. Install with: pip install langchain langchain-openai")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class SupportBot:
    """
    RAG-based Support Bot for MIMIC platform.
    
    Uses OpenAI embeddings and GPT-4o-mini with documentation context
    to answer user questions about the platform.
    """
    
    # System prompt for the AI
    SYSTEM_PROMPT = """You are MIMIC Support Bot, a helpful AI assistant for the MIMIC (Brain Capital) copy trading platform.

Your role is to help users with:
- Setting up their accounts and connecting exchanges
- Understanding trading features (DCA, trailing stop-loss, risk guardrails)
- Troubleshooting common issues
- Explaining subscription plans and payments
- General questions about the platform

Guidelines:
1. Be helpful, friendly, and professional
2. Give clear, concise answers based on the provided documentation
3. If you're not sure about something, say so honestly
4. For security-sensitive topics, remind users to never share API secrets
5. Refer users to admin support for account-specific issues you can't help with

Important: At the end of your response, you MUST provide a confidence score.
Format: Add a line at the very end of your response with: [CONFIDENCE: X.XX]
Where X.XX is a number between 0.00 and 1.00 indicating how confident you are in your answer.
- 0.9-1.0: Very confident, answer is directly from documentation
- 0.7-0.9: Confident, answer is well-supported
- 0.5-0.7: Somewhat confident, may need human verification
- Below 0.5: Not confident, should be reviewed by human support
"""

    def __init__(self, api_key: str = None):
        """
        Initialize the Support Bot.
        
        Args:
            api_key: OpenAI API key. If not provided, reads from config.
        """
        self.api_key = api_key
        self.client = None
        self.embeddings = None
        self.chunks: List[Dict] = []  # In-memory chunk storage
        self.chunk_embeddings: List[List[float]] = []  # In-memory embeddings
        
        # Load configuration
        self._load_config()

        if not self.api_key:
            logger.warning(
                "⚠️ OpenAI API key missing. Set OPENAI_API_KEY env var or Config.OPENAI_API_KEY"
            )
        
        # Initialize OpenAI client
        if self.api_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI client initialized")
        else:
            logger.warning("⚠️ OpenAI client not initialized (missing API key or library)")
        
        # Initialize embeddings
        if self.api_key and LANGCHAIN_AVAILABLE:
            self.embeddings = OpenAIEmbeddings(
                model=self.embedding_model,
                openai_api_key=self.api_key
            )
            logger.info(f"✅ Embeddings initialized with {self.embedding_model}")
    
    def _load_config(self):
        """Load configuration from Config class"""
        try:
            from config import Config
            self.api_key = self.api_key or Config.OPENAI_API_KEY
            self.embedding_model = getattr(Config, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
            self.chat_model = getattr(Config, 'OPENAI_CHAT_MODEL', 'gpt-4o-mini')
            self.confidence_threshold = getattr(Config, 'RAG_CONFIDENCE_THRESHOLD', 0.7)
            self.chunk_size = getattr(Config, 'RAG_CHUNK_SIZE', 500)
            self.chunk_overlap = getattr(Config, 'RAG_CHUNK_OVERLAP', 50)
        except ImportError:
            logger.warning("Could not import Config, using defaults")
            self.api_key = self.api_key or os.environ.get('OPENAI_API_KEY', '')
            self.embedding_model = 'text-embedding-3-small'
            self.chat_model = 'gpt-4o-mini'
            self.confidence_threshold = 0.7
            self.chunk_size = 500
            self.chunk_overlap = 50
    
    def is_available(self) -> bool:
        """Check if the support bot is properly configured and available"""
        return bool(self.client and self.api_key)
    
    def load_chunks_from_db(self):
        """Load document chunks and embeddings from database"""
        try:
            from app import app
            from models import DocumentChunk, db
            
            with app.app_context():
                chunks = DocumentChunk.query.all()
                self.chunks = []
                self.chunk_embeddings = []
                
                for chunk in chunks:
                    self.chunks.append({
                        'id': chunk.id,
                        'source_file': chunk.source_file,
                        'chunk_index': chunk.chunk_index,
                        'content': chunk.content,
                        'metadata': chunk.chunk_metadata
                    })
                    
                    # Parse embedding from JSON string
                    if chunk.embedding:
                        try:
                            embedding = json.loads(chunk.embedding)
                            self.chunk_embeddings.append(embedding)
                        except json.JSONDecodeError:
                            self.chunk_embeddings.append([])
                    else:
                        self.chunk_embeddings.append([])
                
                logger.info(f"✅ Loaded {len(self.chunks)} chunks from database")
                
        except Exception as e:
            logger.error(f"Failed to load chunks from database: {e}")
    
    def _compute_embedding(self, text: str) -> List[float]:
        """
        Compute embedding for a text using OpenAI embeddings.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not self.client:
            return []
        
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding computation failed: {e}")
            return []
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        if NUMPY_AVAILABLE:
            a_np = np.array(a)
            b_np = np.array(b)
            return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))
        else:
            # Pure Python fallback
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x ** 2 for x in a) ** 0.5
            norm_b = sum(x ** 2 for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)
    
    def search_similar_chunks(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for chunks most similar to the query.
        
        Args:
            query: User's question
            top_k: Number of top results to return
            
        Returns:
            List of chunks with similarity scores
        """
        if not self.chunks:
            self.load_chunks_from_db()
        
        if not self.chunks:
            logger.warning("No chunks available for search")
            return []
        
        # Compute query embedding
        query_embedding = self._compute_embedding(query)
        if not query_embedding:
            return []
        
        # Compute similarities
        results = []
        for i, (chunk, embedding) in enumerate(zip(self.chunks, self.chunk_embeddings)):
            if embedding:
                similarity = self._cosine_similarity(query_embedding, embedding)
                results.append({
                    **chunk,
                    'similarity': similarity
                })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]
    
    def _build_context(self, chunks: List[Dict]) -> str:
        """Build context string from retrieved chunks"""
        if not chunks:
            return "No relevant documentation found."
        
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get('source_file', 'Unknown')
            content = chunk.get('content', '')
            similarity = chunk.get('similarity', 0)
            
            context_parts.append(f"[Source: {source}]\n{content}")
        
        return "\n\n---\n\n".join(context_parts)
    
    def _extract_confidence(self, response_text: str) -> Tuple[str, float]:
        """
        Extract confidence score from response text.
        
        Args:
            response_text: Full response including confidence marker
            
        Returns:
            Tuple of (clean_response, confidence_score)
        """
        import re
        
        # Look for confidence marker
        pattern = r'\[CONFIDENCE:\s*([\d.]+)\]'
        match = re.search(pattern, response_text)
        
        if match:
            try:
                confidence = float(match.group(1))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
                # Remove the confidence marker from the response
                clean_response = re.sub(pattern, '', response_text).strip()
                return clean_response, confidence
            except ValueError:
                pass
        
        # Default confidence if not found
        return response_text.strip(), 0.5
    
    def chat(
        self, 
        message: str, 
        session_id: str = None,
        user_id: int = None,
        channel: str = 'web',
        telegram_chat_id: str = None
    ) -> Dict[str, Any]:
        """
        Process a chat message and return AI response.
        
        Args:
            message: User's question
            session_id: Session identifier for conversation tracking
            user_id: User ID if logged in
            channel: 'web' or 'telegram'
            telegram_chat_id: Telegram chat ID if from Telegram
            
        Returns:
            Dictionary with:
            - answer: AI response text
            - confidence: Confidence score (0.0-1.0)
            - sources: List of source documents used
            - ticket_id: Support ticket ID if created (low confidence)
            - conversation_id: Conversation ID for follow-up
        """
        if not self.is_available():
            return {
                'answer': "I'm sorry, but the AI support system is currently unavailable. Please contact a human administrator for assistance.",
                'confidence': 0.0,
                'sources': [],
                'ticket_id': None,
                'conversation_id': None,
                'error': 'Support bot not configured'
            }
        
        # Generate session ID if not provided
        if not session_id:
            session_id = secrets.token_urlsafe(16)
        
        # Get or create conversation
        conversation_id = None
        try:
            from models import SupportConversation, SupportMessage, SupportTicket, db
            from app import app
            
            with app.app_context():
                conversation = SupportConversation.get_or_create(
                    session_id=session_id,
                    user_id=user_id,
                    channel=channel,
                    telegram_chat_id=telegram_chat_id
                )
                conversation_id = conversation.id
                
                # Save user message
                user_msg = SupportMessage(
                    conversation_id=conversation_id,
                    role='user',
                    content=message
                )
                db.session.add(user_msg)
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
        
        # Search for relevant chunks
        similar_chunks = self.search_similar_chunks(message, top_k=5)
        context = self._build_context(similar_chunks)
        
        # Build messages for chat completion
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "system", "content": f"Relevant Documentation:\n\n{context}"},
            {"role": "user", "content": message}
        ]
        
        # Get conversation history for context (last 4 messages)
        try:
            from models import SupportMessage
            from app import app
            
            with app.app_context():
                if conversation_id:
                    history = SupportMessage.query.filter_by(
                        conversation_id=conversation_id
                    ).order_by(SupportMessage.created_at.desc()).limit(5).all()
                    
                    # Insert history before current message (reversed to maintain order)
                    for hist_msg in reversed(history[1:]):  # Skip the message we just added
                        messages.insert(2, {
                            "role": hist_msg.role,
                            "content": hist_msg.content
                        })
        except Exception as e:
            logger.warning(f"Could not load conversation history: {e}")
        
        # Call OpenAI
        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            raw_answer = response.choices[0].message.content
            answer, confidence = self._extract_confidence(raw_answer)
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return {
                'answer': "I'm sorry, I encountered an error while processing your question. Please try again or contact human support.",
                'confidence': 0.0,
                'sources': [],
                'ticket_id': None,
                'conversation_id': conversation_id,
                'error': str(e)
            }
        
        # Prepare sources
        sources = [
            {
                'file': chunk.get('source_file', 'Unknown'),
                'similarity': round(chunk.get('similarity', 0), 3)
            }
            for chunk in similar_chunks[:3]
        ]
        
        # Save AI response and potentially create ticket
        ticket_id = None
        try:
            from models import SupportMessage, SupportTicket, db
            from app import app
            
            with app.app_context():
                # Save AI response
                ai_msg = SupportMessage(
                    conversation_id=conversation_id,
                    role='assistant',
                    content=answer,
                    confidence=confidence,
                    sources=sources
                )
                db.session.add(ai_msg)
                
                # Create ticket if confidence is low
                if confidence < self.confidence_threshold:
                    ticket = SupportTicket.create_from_low_confidence(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        question=message,
                        ai_response=answer,
                        confidence=confidence
                    )
                    ticket_id = ticket.id
                    logger.info(f"📝 Created support ticket #{ticket_id} (confidence: {confidence:.2f})")
                
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to save response: {e}")
        
        return {
            'answer': answer,
            'confidence': confidence,
            'sources': sources,
            'ticket_id': ticket_id,
            'conversation_id': conversation_id,
            'session_id': session_id,
            'needs_human_review': confidence < self.confidence_threshold
        }
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of messages in the conversation
        """
        try:
            from models import SupportConversation, SupportMessage
            from app import app
            
            with app.app_context():
                conversation = SupportConversation.query.filter_by(session_id=session_id).first()
                if not conversation:
                    return []
                
                messages = SupportMessage.query.filter_by(
                    conversation_id=conversation.id
                ).order_by(SupportMessage.created_at.asc()).all()
                
                return [msg.to_dict() for msg in messages]
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []


# Global instance
_support_bot: Optional[SupportBot] = None


def get_support_bot() -> SupportBot:
    """Get or create the global SupportBot instance"""
    global _support_bot
    
    if _support_bot is None:
        _support_bot = SupportBot()
    
    return _support_bot


def chat_with_support(
    message: str,
    session_id: str = None,
    user_id: int = None,
    channel: str = 'web',
    telegram_chat_id: str = None
) -> Dict[str, Any]:
    """
    Convenience function to chat with the support bot.
    
    Args:
        message: User's question
        session_id: Session identifier
        user_id: User ID if logged in
        channel: 'web' or 'telegram'
        telegram_chat_id: Telegram chat ID if from Telegram
        
    Returns:
        Response dictionary from SupportBot.chat()
    """
    bot = get_support_bot()
    return bot.chat(
        message=message,
        session_id=session_id,
        user_id=user_id,
        channel=channel,
        telegram_chat_id=telegram_chat_id
    )


# Test function
if __name__ == '__main__':
    print("Testing Support Bot...")
    print("=" * 60)
    
    bot = SupportBot()
    
    if not bot.is_available():
        print("❌ Support Bot is not available (check OPENAI_API_KEY)")
        exit(1)
    
    print("✅ Support Bot initialized")
    print()
    
    # Test questions
    test_questions = [
        "How do I connect my Binance account?",
        "What is DCA?",
        "How does the referral system work?",
    ]
    
    for question in test_questions:
        print(f"Q: {question}")
        print("-" * 40)
        
        response = bot.chat(question)
        
        print(f"A: {response['answer'][:200]}...")
        print(f"Confidence: {response['confidence']:.2f}")
        print(f"Sources: {[s['file'] for s in response['sources']]}")
        print(f"Needs Human Review: {response.get('needs_human_review', False)}")
        print()
