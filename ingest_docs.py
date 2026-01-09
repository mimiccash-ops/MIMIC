#!/usr/bin/env python3
"""
MIMIC Documentation Ingestion Script

This script reads documentation files (README.md, DEV_MANUAL.md, FAQ.md),
splits them into chunks, generates embeddings using OpenAI, and stores
them in the database for RAG retrieval.

Usage:
    python ingest_docs.py
    python ingest_docs.py --force  # Re-ingest all documents
    python ingest_docs.py --file README.md  # Ingest specific file

Requirements:
    - OPENAI_API_KEY must be set in .env or environment
    - Database migrations must be run first (python migrate_add_support_bot.py)
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Documentation files to ingest
DEFAULT_DOCS = [
    'README.md',
    'DEV_MANUAL.md',
    'FAQ.md',
]


def compute_file_hash(filepath: str) -> str:
    """Compute MD5 hash of a file for change detection"""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def split_into_chunks(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Uses a simple character-based splitter that tries to break on
    paragraph boundaries when possible.
    
    Args:
        text: Full document text
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    # Try to import LangChain's text splitter
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        return splitter.split_text(text)
    except ImportError:
        logger.warning("LangChain not available, using basic splitter")
    
    # Fallback: Basic paragraph-aware chunking
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # If adding this paragraph exceeds chunk size
        if len(current_chunk) + len(para) + 2 > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # If paragraph itself is too long, split it
            if len(para) > chunk_size:
                words = para.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 > chunk_size:
                        chunks.append(current_chunk.strip())
                        # Start new chunk with overlap
                        overlap_words = current_chunk.split()[-10:]
                        current_chunk = ' '.join(overlap_words) + ' '
                    current_chunk += word + ' '
            else:
                current_chunk = para + '\n\n'
        else:
            current_chunk += para + '\n\n'
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def compute_embedding(text: str, client, model: str) -> List[float]:
    """
    Compute embedding for text using OpenAI API.
    
    Args:
        text: Text to embed
        client: OpenAI client instance
        model: Embedding model name
        
    Returns:
        List of floats (embedding vector)
    """
    try:
        response = client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return []


def ingest_document(
    filepath: str,
    client,
    embedding_model: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    force: bool = False
) -> int:
    """
    Ingest a single document into the database.
    
    Args:
        filepath: Path to the document file
        client: OpenAI client instance
        embedding_model: Name of the embedding model
        chunk_size: Chunk size for splitting
        chunk_overlap: Overlap between chunks
        force: Force re-ingestion even if file hasn't changed
        
    Returns:
        Number of chunks ingested
    """
    from models import DocumentChunk, db
    from app import app
    
    if not os.path.exists(filepath):
        logger.warning(f"⚠️ File not found: {filepath}")
        return 0
    
    filename = os.path.basename(filepath)
    file_hash = compute_file_hash(filepath)
    
    with app.app_context():
        # Check if document already ingested with same hash
        existing = DocumentChunk.query.filter_by(source_file=filename).first()
        
        if existing and not force:
            existing_hash = existing.chunk_metadata.get('file_hash') if existing.chunk_metadata else None
            if existing_hash == file_hash:
                logger.info(f"ℹ️ {filename} unchanged, skipping (use --force to re-ingest)")
                return 0
        
        # Delete existing chunks for this file
        deleted = DocumentChunk.query.filter_by(source_file=filename).delete()
        if deleted:
            logger.info(f"🗑️ Deleted {deleted} existing chunks for {filename}")
        db.session.commit()
        
        # Read and split document
        logger.info(f"📄 Reading {filename}...")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chunks = split_into_chunks(content, chunk_size, chunk_overlap)
        logger.info(f"📝 Split into {len(chunks)} chunks")
        
        # Process each chunk
        ingested = 0
        for i, chunk_text in enumerate(chunks):
            logger.info(f"  Processing chunk {i+1}/{len(chunks)}...")
            
            # Compute embedding
            embedding = compute_embedding(chunk_text, client, embedding_model)
            
            if not embedding:
                logger.warning(f"  ⚠️ Failed to compute embedding for chunk {i+1}")
                continue
            
            # Create database record
            chunk = DocumentChunk(
                source_file=filename,
                chunk_index=i,
                content=chunk_text,
                embedding=json.dumps(embedding),
                chunk_metadata={
                    'file_hash': file_hash,
                    'chunk_size': len(chunk_text),
                    'embedding_model': embedding_model,
                    'ingested_at': datetime.now(timezone.utc).isoformat()
                }
            )
            db.session.add(chunk)
            ingested += 1
        
        db.session.commit()
        logger.info(f"✅ Ingested {ingested} chunks from {filename}")
        
        return ingested


def main():
    """Main entry point for document ingestion"""
    parser = argparse.ArgumentParser(
        description='Ingest documentation for MIMIC Support Bot RAG'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force re-ingestion of all documents'
    )
    parser.add_argument(
        '--file', '-i',
        type=str,
        help='Ingest a specific file only'
    )
    parser.add_argument(
        '--chunk-size', '-c',
        type=int,
        default=500,
        help='Chunk size in characters (default: 500)'
    )
    parser.add_argument(
        '--chunk-overlap', '-o',
        type=int,
        default=50,
        help='Chunk overlap in characters (default: 50)'
    )
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║          MIMIC - Documentation Ingestion                     ║
║          Embedding documents for RAG Support Bot             ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Check for OpenAI
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("❌ OpenAI package not installed. Run: pip install openai")
        sys.exit(1)
    
    # Load configuration
    try:
        from config import Config
        api_key = Config.OPENAI_API_KEY
        embedding_model = getattr(Config, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
        chunk_size = args.chunk_size or getattr(Config, 'RAG_CHUNK_SIZE', 500)
        chunk_overlap = args.chunk_overlap or getattr(Config, 'RAG_CHUNK_OVERLAP', 50)
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not load config: {e}")
        api_key = os.environ.get('OPENAI_API_KEY', '')
        embedding_model = 'text-embedding-3-small'
        chunk_size = args.chunk_size
        chunk_overlap = args.chunk_overlap
    
    if not api_key:
        logger.error("❌ OPENAI_API_KEY not set. Add it to .env or set as environment variable.")
        sys.exit(1)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    logger.info(f"✅ OpenAI client initialized (model: {embedding_model})")
    
    # Determine files to ingest
    if args.file:
        files = [args.file]
    else:
        files = DEFAULT_DOCS
    
    # Process each file
    total_chunks = 0
    for filename in files:
        filepath = os.path.join(BASE_DIR, filename)
        
        if not os.path.exists(filepath):
            logger.warning(f"⚠️ File not found: {filepath}")
            continue
        
        chunks = ingest_document(
            filepath=filepath,
            client=client,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            force=args.force
        )
        total_chunks += chunks
    
    print()
    print("=" * 60)
    if total_chunks > 0:
        print(f"✅ Ingestion complete! {total_chunks} total chunks embedded.")
    else:
        print("ℹ️ No new chunks to ingest (documents unchanged or not found).")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Start the application: python app.py")
    print("2. Use the /api/support/chat endpoint or chat widget")
    print("3. Or use /support command in Telegram")
    print()


if __name__ == '__main__':
    main()
