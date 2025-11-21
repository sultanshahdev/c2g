"""
CLI Module - Command-line interface for P2PDocs
Phase 1: User-facing CLI for authentication and document management
"""

import argparse
import sys
import json
from pathlib import Path
from .auth import AuthManager
from .storage import StorageManager


class P2PDocsCLI:
    """Command-line interface for P2PDocs"""
    
    def __init__(self, config_dir: str = None):
        """Initialize CLI with AuthManager and StorageManager"""
        self.config_dir = config_dir or str(Path.home() / ".p2pdocs")
        self.auth = AuthManager(self.config_dir)
        self.storage = StorageManager(self.config_dir)
        self.session_file = Path(self.config_dir) / "session.json"
        self.current_user = self._load_session()
    
    def _load_session(self):
        """Load current user from session file"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    return data.get('username')
            except:
                pass
        return None
    
    def _save_session(self, username):
        """Save current user to session file"""
        Path(self.config_dir).mkdir(parents=True, exist_ok=True)
        with open(self.session_file, 'w') as f:
            json.dump({'username': username}, f)
    
    def _clear_session(self):
        """Clear current session"""
        if self.session_file.exists():
            self.session_file.unlink()
    
    def cmd_register(self, args):
        """Handle user registration"""
        success, message = self.auth.register(args.username, args.password)
        if success:
            print(f"[OK] {message}")
        else:
            print(f"[FAIL] {message}")
        return success
    
    def cmd_login(self, args):
        """Handle user login"""
        success, message = self.auth.login(args.username, args.password)
        if success:
            self.current_user = args.username
            self._save_session(args.username)
            print(f"[OK] {message}")
        else:
            print(f"[FAIL] {message}")
        return success
    
    def cmd_create_doc(self, args):
        """Handle document creation"""
        if not self.current_user:
            print("[FAIL] Please login first")
            return False
        
        success, message = self.storage.create_document(
            args.name,
            self.current_user,
            args.content or ""
        )
        if success:
            print(f"[OK] {message}")
        else:
            print(f"[FAIL] {message}")
        return success
    
    def cmd_read_doc(self, args):
        """Handle document reading"""
        success, content = self.storage.read_document(args.name)
        if success:
            print(f"[OK] Content of '{args.name}':")
            print("-" * 40)
            print(content)
            print("-" * 40)
        else:
            print(f"[FAIL] {content}")
        return success
    
    def cmd_open_doc(self, args):
        """Handle document opening in GUI editor"""
        if not self.current_user:
            print("[FAIL] Please login first")
            return False
        
        try:
            from .gui import P2PDocsEditor
            
            # Verify document exists
            success, content = self.storage.read_document(args.name)
            if not success:
                print(f"[FAIL] Document '{args.name}' not found")
                return False
            
            print(f"[OK] Opening '{args.name}' in GUI editor...")
            editor = P2PDocsEditor(self.current_user, document_name=args.name)
            editor.run()
            return True
        except Exception as e:
            print(f"[FAIL] Could not open document: {e}")
            return False
    
    def cmd_update_doc(self, args):
        """Handle document update"""
        if not self.current_user:
            print("[FAIL] Please login first")
            return False
        
        success, message = self.storage.update_document(args.name, args.content)
        if success:
            print(f"[OK] {message}")
        else:
            print(f"[FAIL] {message}")
        return success
    
    def cmd_delete_doc(self, args):
        """Handle document deletion"""
        if not self.current_user:
            print("[FAIL] Please login first")
            return False
        
        success, message = self.storage.delete_document(args.name)
        if success:
            print(f"[OK] {message}")
        else:
            print(f"[FAIL] {message}")
        return success
    
    def cmd_list_docs(self, args):
        """Handle document listing"""
        docs = self.storage.list_documents()
        if docs:
            print("[OK] Documents:")
            for i, doc in enumerate(docs, 1):
                meta = self.storage.get_document_metadata(doc)
                print(f"  {i}. {doc} (v{meta['version']}, owner: {meta['owner']})")
        else:
            print("[OK] No documents yet")
        return True
    
    def cmd_users(self, args):
        """List all registered users"""
        users = self.auth.get_all_users()
        if users:
            print("[OK] Registered users:")
            for i, user in enumerate(users, 1):
                print(f"  {i}. {user}")
        else:
            print("[OK] No users registered")
        return True
    
    def cmd_edit_gui(self, args):
        """Launch GUI editor for the current user"""
        if not self.current_user:
            print("[FAIL] Please login first")
            return False
        
        try:
            from .gui import P2PDocsEditor
            print(f"[OK] Launching GUI for user '{self.current_user}'...")
            editor = P2PDocsEditor(self.current_user)
            editor.run()
            return True
        except Exception as e:
            print(f"[FAIL] Could not launch GUI: {e}")
            return False
    
    def run(self, argv=None):
        """Main CLI entry point"""
        parser = argparse.ArgumentParser(
            description="P2PDocs - Peer-to-Peer Collaborative Document Editor",
            prog="p2pdocs"
        )
        
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # Register command
        register_parser = subparsers.add_parser("register", help="Register a new user")
        register_parser.add_argument("username", help="Username")
        register_parser.add_argument("password", help="Password")
        register_parser.set_defaults(func=self.cmd_register)
        
        # Login command
        login_parser = subparsers.add_parser("login", help="Login as a user")
        login_parser.add_argument("username", help="Username")
        login_parser.add_argument("password", help="Password")
        login_parser.set_defaults(func=self.cmd_login)
        
        # Create document command
        create_parser = subparsers.add_parser("create", help="Create a new document")
        create_parser.add_argument("name", help="Document name")
        create_parser.add_argument("--content", "-c", help="Initial content", default="")
        create_parser.set_defaults(func=self.cmd_create_doc)
        
        # Read document command
        read_parser = subparsers.add_parser("read", help="Read a document")
        read_parser.add_argument("name", help="Document name")
        read_parser.set_defaults(func=self.cmd_read_doc)
        
        # Open document command
        open_parser = subparsers.add_parser("open", help="Open a document")
        open_parser.add_argument("name", help="Document name")
        open_parser.set_defaults(func=self.cmd_open_doc)
        
        # Update document command
        update_parser = subparsers.add_parser("update", help="Update a document")
        update_parser.add_argument("name", help="Document name")
        update_parser.add_argument("content", help="New content")
        update_parser.set_defaults(func=self.cmd_update_doc)
        
        # Delete document command
        delete_parser = subparsers.add_parser("delete", help="Delete a document")
        delete_parser.add_argument("name", help="Document name")
        delete_parser.set_defaults(func=self.cmd_delete_doc)
        
        # List documents command
        list_parser = subparsers.add_parser("list", help="List all documents")
        list_parser.set_defaults(func=self.cmd_list_docs)
        
        # List users command
        users_parser = subparsers.add_parser("users", help="List all registered users")
        users_parser.set_defaults(func=self.cmd_users)
        
        # Edit GUI command
        edit_parser = subparsers.add_parser("edit", help="Launch GUI text editor")
        edit_parser.set_defaults(func=self.cmd_edit_gui)
        
        args = parser.parse_args(argv)
        
        if not args.command:
            parser.print_help()
            return 0
        
        if hasattr(args, "func"):
            success = args.func(args)
            return 0 if success else 1
        
        return 0


def main():
    """Entry point for CLI"""
    cli = P2PDocsCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
