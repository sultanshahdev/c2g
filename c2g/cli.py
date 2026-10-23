"""
Command-line interface for c2g — Code 2gether.
"""

import argparse


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="c2g trusted-LAN collaborative editor")
    parser.add_argument("username")
    parser.add_argument("peer", nargs="?", help="peer host or host:port")
    parser.add_argument("--listen-port", type=int, default=5000)
    args = parser.parse_args()
    if not 0 <= args.listen_port <= 65535: parser.error("listen port must be 0..65535")
    return args.username, args.peer, args.listen_port


def main():
    """Main entry point for CLI."""
    username, peer_ip, listen_port = parse_args()
    
    from .ui import P2PEditor
    
    print(f"Starting c2g — Code 2gether for user: {username}")
    if peer_ip:
        print(f"Connecting to peer: {peer_ip}")
    
    editor = P2PEditor(username, peer_ip, listen_port)
    editor.run()


if __name__ == "__main__":
    main()
