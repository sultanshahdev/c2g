"""
Command-line interface for P2P CRDT Editor.
"""

import sys


def parse_args():
    """Parse command-line arguments."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Start with discovery: p2pdocs <username>")
        print("  Connect to peer: p2pdocs <username> <peer_ip>")
        print("\nAlternative:")
        print("  python -m p2pdocs <username> [<peer_ip>]")
        sys.exit(1)
    
    username = sys.argv[1]
    peer_ip = sys.argv[2] if len(sys.argv) > 2 else None
    
    return username, peer_ip


def main():
    """Main entry point for CLI."""
    username, peer_ip = parse_args()
    
    from .ui import P2PEditor
    
    print(f"Starting P2P CRDT Editor for user: {username}")
    if peer_ip:
        print(f"Connecting to peer: {peer_ip}")
    
    editor = P2PEditor(username, peer_ip)
    editor.run()


if __name__ == "__main__":
    main()
