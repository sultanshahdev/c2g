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
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--new", action="store_true", help="open the New Document flow")
    group.add_argument("--resume", metavar="STORAGE_KEY", help="resume an exact saved document")
    args = parser.parse_args()
    if not 0 <= args.listen_port <= 65535: parser.error("listen port must be 0..65535")
    if args.resume:
        from .ui.app import DesktopApplication
        if not DesktopApplication.valid_storage_key(args.resume): parser.error("invalid storage key")
    return args.username, args.peer, args.listen_port, args.new, args.resume


def main():
    """Main entry point for CLI."""
    username, peer_ip, listen_port, new, resume = parse_args()
    
    from .ui import DesktopApplication
    
    print(f"Starting c2g — Code 2gether for user: {username}")
    if peer_ip:
        print(f"Connecting to peer: {peer_ip}")
    
    try:
        DesktopApplication(username, peer_ip, listen_port, new=new, resume=resume).run()
    except RuntimeError as exc:
        raise SystemExit(f"c2g could not start the Monaco desktop editor: {exc}") from exc


if __name__ == "__main__":
    main()
