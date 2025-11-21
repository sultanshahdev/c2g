"""
Document Versioning Module
Phase 5: Document version tracking (simplified - no ACL)
"""

import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


class DocumentVersion:
    """Represents a single version of a document"""
    
    def __init__(self, version_num: int, content: str, author: str, 
                 timestamp: str = None, message: str = ""):
        """
        Initialize document version
        
        Args:
            version_num: Version number (1, 2, 3, ...)
            content: Document content at this version
            author: Username of who made this version
            timestamp: ISO format timestamp
            message: Version message/comment
        """
        self.version_num = version_num
        self.content = content
        self.author = author
        self.timestamp = timestamp or datetime.now().isoformat()
        self.message = message
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "version": self.version_num,
            "content": self.content,
            "author": self.author,
            "timestamp": self.timestamp,
            "message": self.message
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'DocumentVersion':
        """Create from dictionary"""
        return DocumentVersion(
            data["version"],
            data["content"],
            data["author"],
            data.get("timestamp"),
            data.get("message", "")
        )


class DocumentHistory:
    """Manages version history for a document"""
    
    def __init__(self, doc_name: str, owner: str):
        """
        Initialize document history
        
        Args:
            doc_name: Name of document
            owner: Username of owner
        """
        self.doc_name = doc_name
        self.owner = owner
        self.versions: List[DocumentVersion] = []
    
    def add_version(self, content: str, author: str, message: str = "") -> int:
        """
        Add a new version
        
        Args:
            content: Document content
            author: Username of author
            message: Version message
            
        Returns:
            New version number
        """
        version_num = len(self.versions) + 1
        version = DocumentVersion(version_num, content, author, message=message)
        self.versions.append(version)
        return version_num
    
    def get_version(self, version_num: int) -> Optional[DocumentVersion]:
        """Get a specific version"""
        if 1 <= version_num <= len(self.versions):
            return self.versions[version_num - 1]
        return None
    
    def get_latest_version(self) -> Optional[DocumentVersion]:
        """Get latest version"""
        return self.versions[-1] if self.versions else None
    
    def get_current_version_number(self) -> int:
        """Get current version number"""
        return len(self.versions)
    
    def get_version_range(self, from_version: int, to_version: Optional[int] = None) -> List[DocumentVersion]:
        """Get range of versions"""
        if to_version is None:
            to_version = len(self.versions)
        
        return [v for v in self.versions if from_version <= v.version_num <= to_version]
    
    def get_history_summary(self) -> list:
        """Get summary of all versions"""
        return [
            {
                "version": v.version_num,
                "author": v.author,
                "timestamp": v.timestamp,
                "message": v.message
            }
            for v in self.versions
        ]
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "doc_name": self.doc_name,
            "owner": self.owner,
            "versions": [v.to_dict() for v in self.versions]
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'DocumentHistory':
        """Create from dictionary"""
        history = DocumentHistory(data["doc_name"], data["owner"])
        
        for v_data in data["versions"]:
            version = DocumentVersion.from_dict(v_data)
            history.versions.append(version)
        
        return history


class VersioningManager:
    """Manages versioning for all documents"""
    
    def __init__(self, storage_dir: str = None):
        """
        Initialize versioning manager
        
        Args:
            storage_dir: Directory to store version history
        """
        if storage_dir is None:
            self.storage_dir = Path.home() / ".p2pdocs" / "history"
        else:
            self.storage_dir = Path(storage_dir)
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.histories: Dict[str, DocumentHistory] = {}
    
    def create_document_history(self, doc_name: str, owner: str, 
                                initial_content: str = "") -> DocumentHistory:
        """Create history for a new document"""
        history = DocumentHistory(doc_name, owner)
        if initial_content:
            history.add_version(initial_content, owner, "Initial version")
        else:
            history.add_version("", owner, "Empty document")
        
        self.histories[doc_name] = history
        self._save_history(history)
        
        return history
    
    def load_history(self, doc_name: str) -> Optional[DocumentHistory]:
        """Load history from storage"""
        if doc_name in self.histories:
            return self.histories[doc_name]
        
        # Try to load from file
        history_file = self.storage_dir / f"{doc_name}.json"
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text())
                history = DocumentHistory.from_dict(data)
                self.histories[doc_name] = history
                return history
            except Exception as e:
                print(f"Error loading history for {doc_name}: {str(e)}")
        
        return None
    
    def update_document(self, doc_name: str, content: str, author: str, 
                       message: str = "") -> int:
        """Update document and save new version"""
        if doc_name not in self.histories:
            raise ValueError(f"Document {doc_name} not in history")
        
        history = self.histories[doc_name]
        version_num = history.add_version(content, author, message)
        self._save_history(history)
        
        return version_num
    
    def get_history(self, doc_name: str) -> Optional[DocumentHistory]:
        """Get document history"""
        return self.load_history(doc_name)
    
    def _save_history(self, history: DocumentHistory):
        """Save history to file"""
        history_file = self.storage_dir / f"{history.doc_name}.json"
        history_file.write_text(json.dumps(history.to_dict(), indent=2))
    
    def cleanup_old_versions(self, doc_name: str, keep_versions: int = 10):
        """Keep only the last N versions to save space"""
        if doc_name not in self.histories:
            return
        
        history = self.histories[doc_name]
        if len(history.versions) > keep_versions:
            history.versions = history.versions[-keep_versions:]
            self._save_history(history)
