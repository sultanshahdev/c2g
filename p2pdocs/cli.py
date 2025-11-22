"""
CLI Module - Simplified entry point for P2PDocs
All functionality is now in the GUI
"""

import argparse
import sys
import json
import logging
from pathlib import Path
from .auth import AuthManager
from .storage import StorageManager
from .network_manager import NetworkManager

# Disable verbose logging from network components
logging.getLogger("p2pdocs.network").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network_manager").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network.server").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network.discovery").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network.client").setLevel(logging.WARNING)


class P2PDocsCLI:
    """Command-line interface for P2PDocs - Simplified to GUI-focused"""
    
    def __init__(self, config_dir: str = None):
        """Initialize CLI"""
        self.config_dir = config_dir or str(Path.home() / ".p2pdocs")
        self.auth = AuthManager(self.config_dir)
        self.session_file = Path(self.config_dir) / "session.json"
    
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
        """Handle user login - Opens GUI with network discovery"""
        success, message = self.auth.login(args.username, args.password)
        if success:
            self._save_session(args.username)
            
            # Initialize and start network manager
            network_manager = NetworkManager(args.username, config_dir=self.config_dir)
            network_manager.start()
            
            print(f"[OK] {message}")
            print(f"[INFO] Launching P2PDocs GUI...")
            
            # Auto-open GUI editor after login (keeps network discovery active)
            try:
                from .gui import P2PDocsEditor
                editor = P2PDocsEditor(
                    args.username,
                    document_name=None,
                    network_manager=network_manager
                )
                # run() blocks until GUI closes, then returns
                editor.run()
                # When we reach here, GUI has closed and network_manager was stopped
                print(f"[INFO] P2PDocs GUI closed. Session ended.")
                self._clear_session()
                return True
            except Exception as e:
                print(f"[FAIL] Could not launch GUI: {e}")
                # Ensure network manager stops even on error
                try:
                    network_manager.stop()
                except:
                    pass
                return False
        else:
            print(f"[FAIL] {message}")
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
        
        # Login command - Only command needed, opens GUI
        login_parser = subparsers.add_parser("login", help="Login and open P2PDocs GUI")
        login_parser.add_argument("username", help="Username")
        login_parser.add_argument("password", help="Password")
        login_parser.set_defaults(func=self.cmd_login)
        
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
