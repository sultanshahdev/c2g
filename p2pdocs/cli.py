"""
CLI Module - Streamlined command-line interface for P2PDocs
Removed redundant commands: read, open, update, create
Kept core functionality: register, login, new, edit, view, delete, list, users
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
    
    def cmd_new_doc(self, args):
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
    
    def cmd_view_doc(self, args):
        """Handle document viewing in terminal"""
        success, content = self.storage.read_document(args.name)
        if success:
            print(f"[OK] Content of '{args.name}':")
            print("-" * 40)
            print(content)
            print("-" * 40)
        else:
            print(f"[FAIL] {content}")
        return success
    
    def cmd_edit_doc(self, args):
        """Handle document editing in GUI editor"""
        if not self.current_user:
            print("[FAIL] Please login first")
            return False
        
        try:
            from .gui import P2PDocsEditor
            
            # If document name provided, open specific document
            if args.name:
                success, content = self.storage.read_document(args.name)
                if not success:
                    print(f"[FAIL] Document '{args.name}' not found")
                    return False
                print(f"[OK] Opening '{args.name}' in GUI editor...")
            else:
                print(f"[OK] Launching GUI editor for user '{self.current_user}'...")
            
            editor = P2PDocsEditor(
                self.current_user,
                document_name=args.name if args.name else None
            )
            editor.run()
            return True
        except Exception as e:
            print(f"[FAIL] Could not launch editor: {e}")
            return False
    
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
        
        # New document command
        new_parser = subparsers.add_parser("new", help="Create a new document")
        new_parser.add_argument("name", help="Document name")
        new_parser.add_argument("--content", "-c", help="Initial content", default="")
        new_parser.set_defaults(func=self.cmd_new_doc)
        
        # View document command
        view_parser = subparsers.add_parser("view", help="View document in terminal")
        view_parser.add_argument("name", help="Document name")
        view_parser.set_defaults(func=self.cmd_view_doc)
        
        # Edit document command (GUI)
        edit_parser = subparsers.add_parser("edit", help="Edit document in GUI")
        edit_parser.add_argument("name", nargs="?", default=None, help="Document name (optional)")
        edit_parser.set_defaults(func=self.cmd_edit_doc)
        
        # Delete document command
        delete_parser = subparsers.add_parser("delete", help="Delete a document")
        delete_parser.add_argument("name", help="Document name")
        delete_parser.set_defaults(func=self.cmd_delete_doc)
        
        # List documents command
        list_parser = subparsers.add_parser("list", help="List all documents")
        list_parser.set_defaults(func=self.cmd_list_docs)
        
        # List users command
        users_parser = subparsers.add_parser("users", help="List registered users")
        users_parser.set_defaults(func=self.cmd_users)
        
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
