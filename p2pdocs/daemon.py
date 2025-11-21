"""
Daemon Module - Background service for P2P network and peer discovery
Allows CLI commands to run independently while network stays active
"""

import os
import sys
import json
import time
import signal
import logging
import threading
from pathlib import Path
from .network_manager import NetworkManager
from .auth import AuthManager

# Suppress network component logging for cleaner output
logging.getLogger("p2pdocs.network").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network_manager").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network.server").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network.discovery").setLevel(logging.WARNING)
logging.getLogger("p2pdocs.network.client").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class P2PDocsDaemon:
    """Background daemon for P2PDocs network management"""
    
    def __init__(self, config_dir: str = None):
        """Initialize daemon"""
        self.config_dir = config_dir or str(Path.home() / ".p2pdocs")
        self.session_file = Path(self.config_dir) / "session.json"
        self.daemon_pid_file = Path(self.config_dir) / "daemon.pid"
        self.network_manager = None
        self.running = False
    
    def is_running(self) -> bool:
        """Check if daemon is already running"""
        if not self.daemon_pid_file.exists():
            return False
        
        try:
            with open(self.daemon_pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process with this PID still exists
            if os.name == 'nt':  # Windows
                import subprocess
                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True)
                return str(pid) in result.stdout.decode()
            else:  # Unix
                os.kill(pid, 0)  # This will raise exception if process doesn't exist
                return True
        except:
            return False
    
    def start(self):
        """Start the daemon"""
        if self.is_running():
            logger.info("Daemon already running")
            return True
        
        # Get current user from session
        current_user = self._get_current_user()
        if not current_user:
            print("[FAIL] No user logged in. Run 'p2pdocs login <username> <password>' first")
            return False
        
        # Save daemon PID
        Path(self.config_dir).mkdir(parents=True, exist_ok=True)
        with open(self.daemon_pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        print(f"[OK] Starting P2PDocs daemon for user '{current_user}'...")
        
        # Initialize network manager
        self.network_manager = NetworkManager(current_user, config_dir=self.config_dir)
        self.network_manager.start()
        
        self.running = True
        print(f"[OK] Daemon started successfully (PID: {os.getpid()})")
        print(f"[INFO] Network discovery active on LAN")
        print(f"[INFO] Use 'p2pdocs stop' to stop the daemon")
        
        # Keep running until interrupted
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the daemon"""
        if not self.is_running():
            print("[INFO] Daemon not running")
            return True
        
        print("[INFO] Stopping daemon...")
        
        if self.network_manager:
            self.network_manager.stop()
        
        self.running = False
        
        # Remove PID file
        if self.daemon_pid_file.exists():
            self.daemon_pid_file.unlink()
        
        print("[OK] Daemon stopped")
        return True
    
    def status(self):
        """Check daemon status"""
        if self.is_running():
            current_user = self._get_current_user()
            print(f"[OK] Daemon is running for user '{current_user}'")
            
            # Show network status if available
            if self.network_manager:
                status = self.network_manager.get_status()
                print(f"[INFO] Network status:")
                print(f"  - TCP Port: {status['tcp_port']}")
                print(f"  - Discovered Peers: {status['discovered_peers']}")
                print(f"  - Connected Peers: {status['connected_peers']}")
        else:
            print("[INFO] Daemon is not running")
            print("[INFO] Run 'p2pdocs daemon start' to start the daemon")
        return True
    
    def _get_current_user(self) -> str:
        """Get currently logged-in user from session"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    return data.get('username')
            except:
                pass
        return None


def daemon_main():
    """Entry point for daemon"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="P2PDocs Daemon - Background network service",
        prog="p2pdocs-daemon"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Daemon commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the daemon")
    start_parser.set_defaults(func="start")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the daemon")
    stop_parser.set_defaults(func="stop")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check daemon status")
    status_parser.set_defaults(func="status")
    
    args = parser.parse_args()
    
    daemon = P2PDocsDaemon()
    
    if not args.command:
        parser.print_help()
        return 0
    
    if args.command == "start":
        daemon.start()
        return 0 if daemon.running else 1
    elif args.command == "stop":
        daemon.stop()
        return 0
    elif args.command == "status":
        daemon.status()
        return 0
    
    return 0


if __name__ == "__main__":
    sys.exit(daemon_main())
