"""
Storage Module - Document and metadata management
Phase 1: Local storage for documents and configuration
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Tuple, Optional, List
from datetime import datetime


class StorageManager:
    """Handles document storage and metadata management"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize StorageManager with configuration directory
        
        Args:
            config_dir: Directory to store documents (default: ~/.p2pdocs)
        """
        if config_dir is None:
            self.config_dir = Path.home() / ".p2pdocs"
        else:
            self.config_dir = Path(config_dir)
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir = self.config_dir / "documents"
        self.documents_dir.mkdir(exist_ok=True)
        self.metadata_file = self.config_dir / "metadata.json"
        self.metadata_lock = threading.RLock()  # Lock for thread-safe metadata operations
        self.file_locks = {}  # Per-file locks for concurrent write protection
        self.file_locks_lock = threading.RLock()  # Lock for managing file_locks dict
        self._ensure_metadata_file()
    
    def _ensure_metadata_file(self):
        """Ensure metadata.json file exists"""
        if not self.metadata_file.exists():
            self.metadata_file.write_text(json.dumps({"documents": {}}, indent=2))
    
    def _get_file_lock(self, doc_name: str) -> threading.RLock:
        """Get or create a lock for a specific document file"""
        with self.file_locks_lock:
            if doc_name not in self.file_locks:
                self.file_locks[doc_name] = threading.RLock()
            return self.file_locks[doc_name]
    
    def _load_metadata(self) -> dict:
        """Load metadata from JSON file with thread safety"""
        with self.metadata_lock:
            try:
                return json.loads(self.metadata_file.read_text())
            except json.JSONDecodeError:
                return {"documents": {}}
    
    def _save_metadata(self, metadata: dict):
        """Save metadata to JSON file with thread-safe atomic write"""
        with self.metadata_lock:
            try:
                # Write to temporary file first, then rename (atomic on most filesystems)
                temp_file = self.metadata_file.with_suffix('.tmp')
                temp_file.write_text(json.dumps(metadata, indent=2))
                # Atomic rename (overwrites metadata_file)
                temp_file.replace(self.metadata_file)
            except Exception as e:
                # If temp file rename fails, at least we didn't corrupt the original
                raise RuntimeError(f"Failed to save metadata: {e}")
    
    def create_document(self, doc_name: str, owner: str, content: str = "") -> Tuple[bool, str]:
        """
        Create a new document with atomic file creation (prevents TOCTOU race)
        
        Args:
            doc_name: Name of document (without .txt extension)
            owner: Username of document owner
            content: Initial content (default: empty string)
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Validate inputs
        if not doc_name or len(doc_name) < 1:
            return False, "Document name cannot be empty"
        
        if not owner:
            return False, "Owner cannot be empty"
        
        # Sanitize document name (remove .txt if provided, prevent path traversal)
        if doc_name.endswith(".txt"):
            doc_name = doc_name[:-4]
        
        if "/" in doc_name or "\\" in doc_name:
            return False, "Invalid characters in document name"
        
        with self.metadata_lock:
            metadata = self._load_metadata()
            
            if doc_name in metadata["documents"]:
                return False, f"Document '{doc_name}' already exists"
            
            # Create document file with O_EXCL to prevent TOCTOU race
            doc_path = self.documents_dir / f"{doc_name}.txt"
            try:
                # O_EXCL ensures atomic create - fails if file exists
                # This prevents race condition where two processes check then both create
                fd = os.open(str(doc_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                try:
                    with os.fdopen(fd, 'w') as f:
                        f.write(content)
                except:
                    # Clean up file if write fails
                    try:
                        doc_path.unlink()
                    except:
                        pass
                    raise
            except FileExistsError:
                return False, f"Document '{doc_name}' already exists (race condition detected)"
            except Exception as e:
                return False, f"Failed to create document: {e}"
            
            # Add metadata
            metadata["documents"][doc_name] = {
                "owner": owner,
                "created_at": datetime.now().isoformat(),
                "version": 1,
                "last_modified": datetime.now().isoformat(),
                "file_path": str(doc_path)
            }
            
            self._save_metadata(metadata)
            return True, f"Document '{doc_name}' created successfully"
    
    def read_document(self, doc_name: str) -> Tuple[bool, Optional[str]]:
        """
        Read document content
        
        Args:
            doc_name: Name of document
            
        Returns:
            Tuple[bool, Optional[str]]: (success, content or error message)
        """
        metadata = self._load_metadata()
        
        if doc_name not in metadata["documents"]:
            return False, f"Document '{doc_name}' not found"
        
        doc_path = self.documents_dir / f"{doc_name}.txt"
        
        if not doc_path.exists():
            return False, f"Document file missing: {doc_name}"
        
        try:
            content = doc_path.read_text()
            return True, content
        except Exception as e:
            return False, f"Error reading document: {str(e)}"
    
    def update_document(self, doc_name: str, content: str) -> Tuple[bool, str]:
        """
        Update document content with file locking to prevent concurrent write races
        
        Args:
            doc_name: Name of document
            content: New content
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        with self.metadata_lock:
            metadata = self._load_metadata()
            
            if doc_name not in metadata["documents"]:
                return False, f"Document '{doc_name}' not found"
            
            doc_path = self.documents_dir / f"{doc_name}.txt"
            
            try:
                # Use per-document lock to prevent concurrent writes (cross-platform)
                file_lock = self._get_file_lock(doc_name)
                with file_lock:
                    with open(doc_path, 'w') as f:
                        f.write(content)
                        f.flush()  # Ensure data written to disk
                        os.fsync(f.fileno())  # Force filesystem sync
                
                # Update metadata
                metadata["documents"][doc_name]["version"] += 1
                metadata["documents"][doc_name]["last_modified"] = datetime.now().isoformat()
                self._save_metadata(metadata)
                
                return True, f"Document '{doc_name}' updated (v{metadata['documents'][doc_name]['version']})"
            except Exception as e:
                return False, f"Error updating document: {str(e)}"
    
    def delete_document(self, doc_name: str) -> Tuple[bool, str]:
        """
        Delete a document with proper locking
        
        Args:
            doc_name: Name of document
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        with self.metadata_lock:
            metadata = self._load_metadata()
            
            if doc_name not in metadata["documents"]:
                return False, f"Document '{doc_name}' not found"
            
            doc_path = self.documents_dir / f"{doc_name}.txt"
            
            try:
                # Delete file if it exists
                if doc_path.exists():
                    doc_path.unlink()
                
                # Remove from metadata
                del metadata["documents"][doc_name]
                self._save_metadata(metadata)
                
                return True, f"Document '{doc_name}' deleted"
            except Exception as e:
                return False, f"Error deleting document: {str(e)}"
    
    def list_documents(self) -> List[str]:
        """
        List all documents
        
        Returns:
            List of document names
        """
        metadata = self._load_metadata()
        return list(metadata["documents"].keys())
    
    def get_document_metadata(self, doc_name: str) -> Optional[dict]:
        """
        Get metadata for a specific document
        
        Args:
            doc_name: Name of document
            
        Returns:
            Document metadata or None if not found
        """
        metadata = self._load_metadata()
        return metadata["documents"].get(doc_name)
    
    def get_document_version(self, doc_name: str) -> Optional[int]:
        """Get current version of a document"""
        doc_meta = self.get_document_metadata(doc_name)
        return doc_meta["version"] if doc_meta else None
