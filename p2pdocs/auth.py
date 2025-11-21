"""
Authentication Module - User registration and login with SHA256 hashing
Phase 1: Foundation for user identity management
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Tuple, Optional


class AuthManager:
    """Handles user registration, login, and password management"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize AuthManager with configuration directory
        
        Args:
            config_dir: Directory to store user credentials (default: ~/.p2pdocs)
        """
        if config_dir is None:
            self.config_dir = Path.home() / ".p2pdocs"
        else:
            self.config_dir = Path(config_dir)
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.users_file = self.config_dir / "users.json"
        self._ensure_users_file()
    
    def _ensure_users_file(self):
        """Ensure users.json file exists"""
        if not self.users_file.exists():
            self.users_file.write_text(json.dumps({}, indent=2))
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password using SHA256
        
        Args:
            password: Plain text password
            
        Returns:
            SHA256 hashed password (hex format)
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _load_users(self) -> dict:
        """Load users from JSON file"""
        try:
            return json.loads(self.users_file.read_text())
        except json.JSONDecodeError:
            return {}
    
    def _save_users(self, users: dict):
        """Save users to JSON file"""
        self.users_file.write_text(json.dumps(users, indent=2))
    
    def register(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Register a new user with username and password
        
        Args:
            username: Desired username
            password: Desired password
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Validate inputs
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters"
        
        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters"
        
        users = self._load_users()
        
        if username in users:
            return False, f"User '{username}' already exists"
        
        # Hash and store password
        hashed_pw = self._hash_password(password)
        users[username] = {
            "password_hash": hashed_pw,
            "created_at": str(Path(self.config_dir).stat().st_ctime)
        }
        
        self._save_users(users)
        return True, f"User '{username}' registered successfully"
    
    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Verify user credentials
        
        Args:
            username: Username to verify
            password: Password to verify
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        users = self._load_users()
        
        if username not in users:
            return False, f"User '{username}' not found"
        
        stored_hash = users[username]["password_hash"]
        provided_hash = self._hash_password(password)
        
        if stored_hash == provided_hash:
            return True, f"Login successful for user '{username}'"
        else:
            return False, "Invalid password"
    
    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        users = self._load_users()
        return username in users
    
    def get_all_users(self) -> list:
        """Get list of all registered usernames"""
        users = self._load_users()
        return list(users.keys())
