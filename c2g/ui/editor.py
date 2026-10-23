"""
P2P collaborative text editor UI.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import time
import hashlib
import uuid
import queue
from datetime import datetime

from ..crdt import CRDTDocument, CRDTMessage, CRDTElement, CRDTId
from ..network import NetworkManager, PeerDiscovery
from . import styles


class P2PEditor:
    """True P2P CRDT editor - all peers are equal."""
    
    def __init__(self, username: str, peer_ip: str = None, listen_port: int = 5000):
        self.username = username
        self.client_id = str(uuid.uuid4())
        # Always start with fresh document (start_fresh=True by default)
        self.doc = CRDTDocument(self.client_id, doc_name="collaborative_doc", start_fresh=True)
        self.document_id = str(uuid.uuid4())
        self.net = NetworkManager(username, listen_port, document_id=self.document_id,
                                  state_provider=self.doc.get_full_state,
                                  is_document_empty=lambda: not self.doc.elements)
        self.discovery = PeerDiscovery(username, peer_id=self.net.peer_id)
        self.discovered_peers = {}
        self.network_events = queue.Queue()
        
        self.root = tk.Tk()
        self.root.title(f"c2g — Code 2gether - {self.username}")
        self.root.geometry("1100x700")
        self.root.configure(bg="#F0F2F5")
        
        self._setup_ui()
        
        self.running = True
        self.text_lock = threading.RLock()
        
        # Start listening for incoming connections
        self.net.on_message = self._on_network_message
        self.net.on_event = lambda kind, data: self.network_events.put((kind, data))
        self.net.start_listening()
        self.root.after(100, self._drain_network_events)
        
        # Start discovery
        threading.Thread(target=self.discovery.start_broadcast, args=(self.net.port,), daemon=True).start()
        threading.Thread(target=self._discovery_monitor, daemon=True).start()
        
        # If peer_ip provided, connect to it
        if peer_ip:
            threading.Thread(target=self._connect_to_peer, args=(peer_ip,), daemon=True).start()
        
        self._periodic_sync()
    
    def _setup_ui(self):
        """Setup modern UI matching the web design."""
        
        # Top Navigation Bar
        header = tk.Frame(self.root, bg="white", height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        
        # Left side of header
        left_header = tk.Frame(header, bg="white")
        left_header.pack(side=tk.LEFT, padx=20, pady=10)
        
        # Icon placeholder
        icon_label = tk.Label(left_header, text="CE", font=("Arial", 14, "bold"), 
                             bg=styles.PRIMARY, fg="white", width=3, height=1)
        icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        title_label = tk.Label(left_header, text="c2g — Code 2gether",
                              font=("Arial", 12, "bold"), bg="white", fg=styles.TEXT_DARK)
        title_label.pack(side=tk.LEFT)
        
        # Center stats (only show on wider windows)
        center_header = tk.Frame(header, bg="white")
        center_header.pack(side=tk.LEFT, expand=True, padx=40)
        
        # Connected peers
        peers_frame = tk.Frame(center_header, bg="white")
        peers_frame.pack(side=tk.LEFT, padx=10)
        self.peers_status_label = tk.Label(peers_frame, text="Connected to 0 Peers", 
                                           font=("Arial", 9), bg="white", fg=styles.GREEN)
        self.peers_status_label.pack(side=tk.LEFT)
        
        # Words count
        words_frame = tk.Frame(center_header, bg="white")
        words_frame.pack(side=tk.LEFT, padx=10)
        self.words_label = tk.Label(words_frame, text="0 Words", 
                                   font=("Arial", 9), bg="white", fg=styles.TEXT_GRAY)
        self.words_label.pack(side=tk.LEFT)
        
        # Chars count
        chars_frame = tk.Frame(center_header, bg="white")
        chars_frame.pack(side=tk.LEFT, padx=10)
        self.chars_label = tk.Label(chars_frame, text="TT 0 Chars", 
                                   font=("Arial", 9), bg="white", fg=styles.TEXT_GRAY)
        self.chars_label.pack(side=tk.LEFT)
        
        # Right side of header
        right_header = tk.Frame(header, bg="white")
        right_header.pack(side=tk.RIGHT, padx=20, pady=8)
        
        # Save button
        share_btn = tk.Button(right_header, text="Save", 
                             bg=styles.PRIMARY, fg="white", font=("Arial", 9, "bold"),
                             relief=tk.FLAT, padx=15, pady=5, cursor="hand2",
                             command=self._save_snapshot)
        share_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # User avatar (using initials)
        avatar_label = tk.Label(right_header, text=self.username[:2].upper(), 
                               font=("Arial", 10, "bold"), bg=styles.PRIMARY, fg="white",
                               width=3, height=1, relief=tk.FLAT)
        avatar_label.pack(side=tk.LEFT)
        
        # Header separator
        tk.Frame(self.root, bg=styles.BORDER_COLOR, height=1).pack(fill=tk.X)
        
        # Main container
        main_container = tk.Frame(self.root, bg=styles.BG_LIGHT)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        sidebar = tk.Frame(main_container, bg=styles.BG_SIDEBAR_OPACITY, width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Sidebar separator
        tk.Frame(sidebar, bg=styles.BORDER_COLOR, width=1).pack(side=tk.RIGHT, fill=tk.Y)
        
        # Sidebar content container
        sidebar_content = tk.Frame(sidebar, bg=styles.BG_SIDEBAR_OPACITY)
        sidebar_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # User profile section
        profile_frame = tk.Frame(sidebar_content, bg=styles.BG_SIDEBAR_OPACITY)
        profile_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Avatar
        avatar = tk.Label(profile_frame, text=self.username[:2].upper(), 
                         font=("Arial", 12, "bold"), bg=styles.PRIMARY, fg="white",
                         width=4, height=2)
        avatar.pack(side=tk.LEFT, padx=(0, 10))
        
        # Profile info
        profile_info = tk.Frame(profile_frame, bg=styles.BG_SIDEBAR_OPACITY)
        profile_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(profile_info, text=f"{self.username}'s Document", 
                font=("Arial", 10, "bold"), bg=styles.BG_SIDEBAR_OPACITY, fg=styles.TEXT_DARK,
                anchor="w").pack(fill=tk.X)
        tk.Label(profile_info, text="Connected Users", 
                font=("Arial", 8), bg=styles.BG_SIDEBAR_OPACITY, fg=styles.TEXT_GRAY,
                anchor="w").pack(fill=tk.X)
        
        # Peers section
        peers_header = tk.Label(sidebar_content, text="PEERS", 
                               font=("Arial", 8, "bold"), bg=styles.BG_SIDEBAR_OPACITY, 
                               fg=styles.TEXT_LIGHT, anchor="w")
        peers_header.pack(fill=tk.X, pady=(10, 5))
        
        # Peers list container with scrollbar
        peers_container = tk.Frame(sidebar_content, bg=styles.BG_SIDEBAR_OPACITY)
        peers_container.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Canvas for scrolling
        canvas = tk.Canvas(peers_container, bg=styles.BG_SIDEBAR_OPACITY, 
                          highlightthickness=0, height=200)
        scrollbar = tk.Scrollbar(peers_container, orient="vertical", command=canvas.yview)
        self.peers_list_frame = tk.Frame(canvas, bg=styles.BG_SIDEBAR_OPACITY)
        
        self.peers_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.peers_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Spacer to push Quick Connect to bottom
        tk.Frame(sidebar_content, bg=styles.BG_SIDEBAR_OPACITY).pack(fill=tk.BOTH, expand=True)
        
        # Quick Connect section
        quick_connect_frame = tk.Frame(sidebar_content, bg=styles.BG_SIDEBAR_OPACITY)
        quick_connect_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        
        tk.Label(quick_connect_frame, text="Quick Connect", 
                font=("Arial", 10, "bold"), bg=styles.BG_SIDEBAR_OPACITY, fg=styles.TEXT_DARK,
                anchor="w").pack(fill=tk.X, pady=(0, 8))
        
        # Input with icon
        input_frame = tk.Frame(quick_connect_frame, bg="white", relief=tk.FLAT)
        input_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.ip_entry = tk.Entry(input_frame, font=("Arial", 9), 
                                bg="white", fg=styles.TEXT_DARK, relief=tk.FLAT,
                                highlightthickness=1, highlightbackground=styles.BORDER_COLOR,
                                highlightcolor=styles.PRIMARY)
        self.ip_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.ip_entry.insert(0, "Enter peer IP address...")
        self.ip_entry.bind("<FocusIn>", lambda e: self.ip_entry.delete(0, tk.END) if self.ip_entry.get() == "Enter peer IP address..." else None)
        
        tk.Label(input_frame, text="→", font=("Arial", 10), 
                bg="white", fg=styles.TEXT_GRAY).pack(side=tk.RIGHT, padx=10)
        
        # Connect button
        connect_btn = tk.Button(quick_connect_frame, text="Connect", 
                               command=self._manual_connect,
                               bg=styles.PRIMARY, fg="white", font=("Arial", 9, "bold"),
                               relief=tk.FLAT, cursor="hand2", pady=8)
        connect_btn.pack(fill=tk.X)
        
        # Main content area
        content_area = tk.Frame(main_container, bg=styles.BG_LIGHT)
        content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Content padding frame
        content_padding = tk.Frame(content_area, bg=styles.BG_LIGHT)
        content_padding.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)
        
        # White paper card
        paper_card = tk.Frame(content_padding, bg="white", relief=tk.FLAT,
                             highlightthickness=1, highlightbackground="#e0e0e0")
        paper_card.pack(fill=tk.BOTH, expand=True)
        
        # Welcome message
        welcome_frame = tk.Frame(paper_card, bg="white")
        welcome_frame.pack(fill=tk.X, padx=30, pady=(30, 0))
        
        welcome_text = ("Welcome to the collaborative editor! Start typing below. "
                       "Your changes will be synced in real-time with your connected peers. "
                       "To Save the current state of the document, click on 'Save' Button.")
        
        welcome_label = tk.Label(welcome_frame, text=welcome_text, 
                                font=("Arial", 10), bg="white", fg=styles.TEXT_GRAY,
                                wraplength=700, justify="left", anchor="w")
        welcome_label.pack(fill=tk.X, pady=(0, 15))
        
        # Separator line
        tk.Frame(welcome_frame, bg=styles.BORDER_COLOR, height=1).pack(fill=tk.X, pady=(0, 15))
        
        # Text editor
        text_frame = tk.Frame(paper_card, bg="white")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 30))
        
        self.text = tk.Text(text_frame, wrap=tk.WORD, 
                           font=("Arial", 11), bg="white", fg=styles.TEXT_DARK,
                           relief=tk.FLAT, highlightthickness=0,
                           undo=True, maxundo=-1, padx=5, pady=5)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.bind("<Key>", self._on_keystroke)
        
        # Footer bar
        footer = tk.Frame(content_area, bg="#fafafa", height=40)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)
        
        # Footer separator
        tk.Frame(footer, bg=styles.BORDER_COLOR, height=1).pack(fill=tk.X, side=tk.TOP)
        
        footer_content = tk.Frame(footer, bg="#fafafa")
        footer_content.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # Left side - sync status
        self.sync_status_label = tk.Label(footer_content, text="Synced", 
                                         font=("Arial", 8), bg="#fafafa", fg=styles.TEXT_GRAY)
        self.sync_status_label.pack(side=tk.LEFT, pady=10)
        
        # Right side - last change
        self.last_change_label = tk.Label(footer_content, text="Last change: a few seconds ago", 
                                         font=("Arial", 8), bg="#fafafa", fg=styles.TEXT_GRAY)
        self.last_change_label.pack(side=tk.RIGHT, pady=10)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _discovery_monitor(self):
        """Monitor discovered peers and update UI."""
        while self.running:
            try:
                self.discovered_peers = self.discovery.get_peers()
                self.network_events.put(("discovery_changed", {}))
                
                time.sleep(2)
            except Exception as e:
                print(f"[{self.username}] Discovery monitor error: {e}")
                time.sleep(2)

    def _drain_network_events(self):
        """Only this Tk-main-thread callback touches network UI state."""
        changed = False
        try:
            while True:
                kind, data = self.network_events.get_nowait(); changed = True
                if kind in ("peer_connected", "sync_complete", "peer_disconnected", "peer_rejected", "connection_error"):
                    detail = data.get("error", "")
                    label = {"peer_connected":"Connecting", "sync_complete":"Synced", "peer_disconnected":"Disconnected",
                             "peer_rejected":"Rejected", "connection_error":"Connection failed"}.get(kind, kind)
                    self.sync_status_label.config(text=f"{label}{': ' + detail if detail else ''}")
        except queue.Empty:
            pass
        if changed: self._update_peer_lists()
        if self.running: self.root.after(100, self._drain_network_events)
    
    def _update_peer_lists(self):
        """Update the peers list in the sidebar."""
        try:
            # Clear existing peer widgets
            for widget in self.peers_list_frame.winfo_children():
                widget.destroy()
            
            with self.net.peers_lock:
                peer_count = len(self.net.peers)
                
                if peer_count == 0:
                    # No peers message
                    no_peers = tk.Label(self.peers_list_frame, text="No connected peers", 
                                       font=("Arial", 9), bg="#fcfcfc", fg="#9ca3af")
                    no_peers.pack(pady=20)
                else:
                    # Show connected peers
                    for idx, (peer_id, session) in enumerate(list(self.net.peers.items())):
                        username = session.username
                        # Create peer card
                        is_first = (idx == 0)
                        peer_frame = tk.Frame(self.peers_list_frame, 
                                            bg=styles.BG_HIGHLIGHT if is_first else "#fcfcfc",
                                            highlightthickness=0)
                        peer_frame.pack(fill=tk.X, padx=5, pady=2)
                        
                        # Avatar with initial
                        color = styles.AVATAR_COLORS[idx % len(styles.AVATAR_COLORS)]
                        
                        avatar_container = tk.Frame(peer_frame, bg=styles.BG_HIGHLIGHT if is_first else "#fcfcfc")
                        avatar_container.pack(side=tk.LEFT, padx=8, pady=8)
                        
                        avatar = tk.Label(avatar_container, text=username[:1].upper(), 
                                        font=("Arial", 10, "bold"), bg=color, fg="white",
                                        width=3, height=1)
                        avatar.pack(side=tk.LEFT)
                        
                        # Green online dot (positioned next to avatar, not overlapping)
                        dot = tk.Label(avatar_container, text="●", 
                                     font=("Arial", 6), bg=styles.BG_HIGHLIGHT if is_first else "#fcfcfc", 
                                     fg=styles.GREEN)
                        dot.pack(side=tk.LEFT, padx=(0, 0))
                        
                        # Username
                        name_label = tk.Label(peer_frame, text=username, 
                                            font=("Arial", 9), 
                                            bg=styles.BG_HIGHLIGHT if is_first else "#fcfcfc", 
                                            fg=styles.TEXT_DARK, anchor="w")
                        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)

            # Discovery is intentionally separate: receiving an announcement
            # never opens a session. The button is the explicit join action.
            connected = set(self.net.peers)
            for peer_id, (username, port, _seen, host) in sorted(self.discovered_peers.items()):
                if peer_id in connected:
                    continue
                frame = tk.Frame(self.peers_list_frame, bg="#fcfcfc")
                frame.pack(fill=tk.X, padx=5, pady=2)
                tk.Label(frame, text=f"{username} (discovered {host}:{port})", font=("Arial", 8), bg="#fcfcfc",
                         fg=styles.TEXT_GRAY, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, pady=6)
                tk.Button(frame, text="Connect", font=("Arial", 8), command=lambda h=host, p=port: self._connect_discovered(h, p)).pack(side=tk.RIGHT, padx=4)
            
            # Update header stats
            self.peers_status_label.config(text=f"Connected to {peer_count} Peer{'s' if peer_count != 1 else ''}")
            
        except Exception as e:
            print(f"[{self.username}] Update peer lists error: {e}")
    
    def _connect_to_peer(self, peer_ip: str):
        """Connect to peer."""
        time.sleep(1)
        host, sep, raw_port = peer_ip.rpartition(":")
        self.net.connect_to_peer(host if sep else peer_ip, int(raw_port) if sep else 5000)
    
    def _manual_connect(self):
        """Connect to manually entered IP."""
        ip = self.ip_entry.get().strip()
        if ip and ip != "Enter peer IP address...":
            print(f"[{self.username}] Manually connecting to {ip}")
            threading.Thread(target=self._connect_to_peer, args=(ip,), daemon=True).start()
            self.ip_entry.delete(0, tk.END)
            self.ip_entry.insert(0, "Enter peer IP address...")
        else:
            messagebox.showwarning("No IP", "Please enter an IP address to connect.")

    def _connect_discovered(self, host, port):
        self.sync_status_label.config(text=f"Connecting to {host}:{port}")
        threading.Thread(target=self.net.connect_to_peer, args=(host, port), daemon=True).start()
    
    def _on_cursor_move(self, event=None):
        """Handle cursor movement (arrow keys, mouse clicks, etc)."""
        # Removed cursor presence functionality
        pass
    
    def _save_snapshot(self):
        """Save current document to a file."""
        try:
            # Get current document content
            content = self.doc.get_text()
            
            if not content.strip():
                messagebox.showwarning("Empty Document", "Cannot save an empty document.")
                return
            
            # Open file dialog to choose save location
            file_path = filedialog.asksaveasfilename(
                title="Save Document Snapshot",
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ],
                initialfile=f"p2p_doc_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            )
            
            if file_path:
                # Write content to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Update status
                messagebox.showinfo("Save Successful", f"Document saved to:\n{file_path}")
                print(f"[{self.username}] Document snapshot saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save document:\n{str(e)}")
            print(f"[{self.username}] Save error: {e}")
    
    def _on_keystroke(self, event):
        """Handle keystroke."""
        if not self.running:
            return
        
        ch = event.char
        keysym = event.keysym
        
        # Check if there's a selection - if so, handle deletion/replacement first
        try:
            if self.text.tag_ranges(tk.SEL):
                sel_start = self.text.index(tk.SEL_FIRST)
                sel_end = self.text.index(tk.SEL_LAST)
                start_pos = len(self.text.get("1.0", sel_start))
                end_pos = len(self.text.get("1.0", sel_end))
                chars_to_delete = end_pos - start_pos
                
                # If typing a character, it will replace selection
                # If pressing backspace/delete, it will delete selection
                if keysym in ('BackSpace', 'Delete') or (ch and len(ch) == 1 and (ch in "\n\t" or 32 <= ord(ch) <= 0x10FFFF)):
                    # Delete the selection from CRDT
                    def process_selection_delete():
                        with self.text_lock:
                            # Collect all deleted char_ids for batching
                            deleted_ids = []
                            # Delete from right to left to maintain positions
                            for i in range(chars_to_delete):
                                delete_pos = end_pos - 1 - i
                                char_id = self.doc.delete_local(delete_pos)
                                if char_id:
                                    deleted_ids.append({
                                        "client_id": char_id.client_id,
                                        "lamport_clock": char_id.lamport_clock
                                    })
                            
                            # Send single batched message instead of many individual ones
                            if deleted_ids:
                                msg = CRDTMessage(msg_type="BATCH_DELETE", char_ids=deleted_ids)
                                self.net.broadcast_message(msg)
                                print(f"[{self.username}] Sent BATCH_DELETE with {len(deleted_ids)} deletions")
                            
                            self._update_stats()
                    
                    self.root.after(1, process_selection_delete)
                    
                    # If it's a character (not just delete), let it insert after deletion
                    if keysym not in ('BackSpace', 'Delete'):
                        # Let Tkinter replace selection with character
                        # Then schedule the insert
                        def process_insert_after_delete():
                            with self.text_lock:
                                elem = self.doc.insert_local(ch if ch else '\n', start_pos)
                                msg = CRDTMessage(msg_type="INSERT", elements=[elem.to_dict()])
                                self.net.broadcast_message(msg)
                                self._update_stats()
                        
                        self.root.after(2, process_insert_after_delete)
                    
                    # Let Tkinter handle the visual change
                    return
        except tk.TclError:
            pass  # No selection
        
        # Handle Return/Enter key explicitly
        if keysym == 'Return':
            # Get position BEFORE Tkinter processes the key
            tk_pos = self.text.index(tk.INSERT)
            position = len(self.text.get("1.0", tk_pos))
            
            # Schedule CRDT update after Tkinter processes the keystroke
            def process_insert():
                with self.text_lock:
                    elem = self.doc.insert_local('\n', position)
                    msg = CRDTMessage(msg_type="INSERT", elements=[elem.to_dict()])
                    print(f"[{self.username}] Sending INSERT: '\\n' (newline)")
                    self.net.broadcast_message(msg)
                    self._update_stats()
            
            self.root.after(1, process_insert)
            # Let Tkinter handle the insert naturally
        
        elif ch and len(ch) == 1 and (ch in "\n\t" or 32 <= ord(ch) <= 0x10FFFF) and not (event.state & 0x0004):
            # Get position BEFORE Tkinter processes the key
            tk_pos = self.text.index(tk.INSERT)
            position = len(self.text.get("1.0", tk_pos))
            
            # Let Tkinter handle the visual insert first (don't return "break" yet)
            # Schedule CRDT update after Tkinter processes the keystroke
            def process_insert():
                with self.text_lock:
                    elem = self.doc.insert_local(ch, position)
                    msg = CRDTMessage(msg_type="INSERT", elements=[elem.to_dict()])
                    print(f"[{self.username}] Sending INSERT: '{ch}'")
                    self.net.broadcast_message(msg)
                    self._update_stats()
            
            self.root.after(1, process_insert)
            # Let Tkinter handle the insert naturally (don't return "break")
        
        if event.keysym == 'BackSpace':
            # Check if Ctrl is pressed (Ctrl+Backspace = delete word)
            if event.state & 0x0004:  # Control key
                # Get current cursor position
                tk_pos = self.text.index(tk.INSERT)
                position = len(self.text.get("1.0", tk_pos))
                
                if position > 0:
                    # Find start of current word
                    content = self.doc.get_text()
                    
                    # Move back to find word boundary
                    start_pos = position - 1
                    
                    # Skip any trailing whitespace first
                    while start_pos >= 0 and content[start_pos] in ' \t\n':
                        start_pos -= 1
                    
                    # Now delete until we hit whitespace or start
                    while start_pos >= 0 and content[start_pos] not in ' \t\n':
                        start_pos -= 1
                    
                    start_pos += 1  # Move to first char of word
                    chars_to_delete = position - start_pos
                    
                    if chars_to_delete > 0:
                        # Delete the word from text widget first
                        delete_start = self.text.index(f"{tk_pos} - {chars_to_delete}c")
                        self.text.delete(delete_start, tk_pos)
                        
                        # Schedule CRDT updates for each character
                        def process_word_delete():
                            with self.text_lock:
                                # Collect all deleted char_ids for batching
                                deleted_ids = []
                                # Delete from right to left to maintain positions
                                for i in range(chars_to_delete):
                                    delete_pos = position - 1 - i
                                    char_id = self.doc.delete_local(delete_pos)
                                    if char_id:
                                        deleted_ids.append({
                                            "client_id": char_id.client_id,
                                            "lamport_clock": char_id.lamport_clock
                                        })
                                
                                # Send batched message for word deletion
                                if deleted_ids:
                                    msg = CRDTMessage(msg_type="BATCH_DELETE", char_ids=deleted_ids)
                                    self.net.broadcast_message(msg)
                                
                                self._update_stats()
                        
                        self.root.after(1, process_word_delete)
                        return "break"
            else:
                # Normal backspace
                # Get position BEFORE Tkinter processes backspace
                tk_pos = self.text.index(tk.INSERT)
                position = len(self.text.get("1.0", tk_pos))
                
                if position > 0:
                    position -= 1
                    
                    # Schedule CRDT update after Tkinter processes the backspace
                    def process_delete():
                        with self.text_lock:
                            char_id = self.doc.delete_local(position)
                            if char_id:
                                print(f"[{self.username}] DELETE at position {position}: ID=({char_id.client_id[:8]}..., {char_id.lamport_clock})")
                                msg = CRDTMessage(msg_type="DELETE", char_id={
                                    "client_id": char_id.client_id,
                                    "lamport_clock": char_id.lamport_clock
                                })
                                self.net.broadcast_message(msg)
                                print(f"[{self.username}] DELETE broadcasted to all peers")
                                self._update_stats()
                            else:
                                print(f"[{self.username}] DELETE failed: No element at position {position}")
                    
                    self.root.after(1, process_delete)
                    # Let Tkinter handle the backspace naturally
    
    def _on_network_message(self, msg: CRDTMessage):
        """Handle incoming message with error handling."""
        try:
            if msg.msg_type == "INSERT":
                for elem_dict in msg.elements:
                    try:
                        elem = CRDTElement.from_dict(elem_dict)
                        if self.doc.insert_remote(elem):
                            self.root.after(0, self._rebuild_text)
                    except (KeyError, ValueError, TypeError) as e:
                        print(f"[{self.username}] Malformed INSERT element (skipping): {e}")
                        continue
            
            elif msg.msg_type == "DELETE":
                try:
                    if not msg.char_id:
                        raise ValueError("DELETE message missing char_id")
                    cid = msg.char_id
                    if not isinstance(cid, dict) or "client_id" not in cid or "lamport_clock" not in cid:
                        raise ValueError("char_id must have client_id and lamport_clock")
                    char_id = CRDTId(cid["client_id"], cid["lamport_clock"])
                    if self.doc.delete_remote(char_id):
                        self.root.after(0, self._rebuild_text)
                except (KeyError, ValueError, TypeError) as e:
                    print(f"[{self.username}] Malformed DELETE message (skipping): {e}")
            
            elif msg.msg_type == "BATCH_DELETE":
                try:
                    if not msg.char_ids:
                        raise ValueError("BATCH_DELETE message missing char_ids")
                    
                    print(f"[{self.username}] Processing BATCH_DELETE with {len(msg.char_ids)} deletions")
                    print(f"[{self.username}] Current document has {len(self.doc.elements)} total elements")
                    
                    deleted_count = 0
                    missing_count = 0
                    already_applied = 0
                    
                    for cid_dict in msg.char_ids:
                        if not isinstance(cid_dict, dict) or "client_id" not in cid_dict or "lamport_clock" not in cid_dict:
                            continue
                        char_id = CRDTId(cid_dict["client_id"], cid_dict["lamport_clock"])
                        
                        # Debug: check if element exists
                        with self.doc.lock:
                            op_key = f"{char_id.client_id}:{char_id.lamport_clock}"
                            exists = char_id in self.doc.elements
                            in_applied = op_key in self.doc.applied_ops
                            
                            print(f"[{self.username}] Delete char_id ({char_id.client_id[:8]}..., {char_id.lamport_clock}): exists={exists}, already_applied={in_applied}")
                        
                        result = self.doc.delete_remote(char_id)
                        if result:
                            deleted_count += 1
                        else:
                            # Check why it failed
                            with self.doc.lock:
                                if op_key in self.doc.applied_ops:
                                    already_applied += 1
                                elif char_id not in self.doc.elements:
                                    missing_count += 1
                    
                    print(f"[{self.username}] BATCH_DELETE results: deleted={deleted_count}, missing={missing_count}, already_applied={already_applied}")
                    
                    # Rebuild only once after all deletes
                    if deleted_count > 0:
                        print(f"[{self.username}] Applied {deleted_count} deletions, rebuilding text")
                        self.root.after(0, self._rebuild_text)
                    elif missing_count > 0:
                        print(f"[{self.username}] WARNING: {missing_count} elements to delete don't exist! Requesting full sync...")
                        # Request full sync from peers
                        sync_req = CRDTMessage(msg_type="SYNC_REQUEST")
                        self.net.broadcast_message(sync_req)
                except (KeyError, ValueError, TypeError) as e:
                    print(f"[{self.username}] Malformed BATCH_DELETE message (skipping): {e}")
            
            elif msg.msg_type == "SYNC_REQUEST":
                elements = self.doc.get_full_state()
                response = CRDTMessage(msg_type="FULL_SYNC", elements=elements)
                self.net.broadcast_message(response)
            
            elif msg.msg_type == "FULL_SYNC":
                try:
                    self.doc.apply_full_state(msg.elements)
                    self.root.after(0, self._rebuild_text)
                except Exception as e:
                    print(f"[{self.username}] Error applying full sync: {e}")
            
            self.root.after(0, self._update_stats)
        except Exception as e:
            print(f"[{self.username}] Message error: {e}")
    
    def _rebuild_text(self, local_insert_offset=0):
        """Rebuild text display, preserving cursor position.
        
        Args:
            local_insert_offset: Offset to add to cursor position after rebuild
                                (e.g., +1 for local character insert)
        """
        try:
            with self.text_lock:
                # Save cursor position as character count
                old_pos_str = self.text.index(tk.INSERT)
                old_char_pos = len(self.text.get("1.0", old_pos_str))
                
                # Get new content
                content = self.doc.get_text()
                
                # Only rebuild if content changed
                current_content = self.text.get("1.0", tk.END).rstrip('\n')
                if current_content == content:
                    return
                
                # Replace content
                self.text.delete("1.0", tk.END)
                self.text.insert("1.0", content)
                
                # Restore cursor: clamp to valid position, add offset for local inserts
                max_pos = len(content)
                new_char_pos = min(old_char_pos + local_insert_offset, max_pos)
                
                # Convert character position to Tkinter index (line.col)
                if new_char_pos == 0:
                    new_pos = "1.0"
                else:
                    # Count newlines before position to find line number
                    text_before = content[:new_char_pos]
                    lines = text_before.split('\n')
                    line_num = len(lines)
                    col_num = len(lines[-1])
                    new_pos = f"{line_num}.{col_num}"
                
                self.text.mark_set(tk.INSERT, new_pos)
        except Exception as e:
            print(f"[{self.username}] Rebuild error: {e}")
    
    def _update_stats(self):
        """Update statistics in header and footer."""
        try:
            with self.text_lock:
                content = self.doc.get_text()
                char_count = len(content)
                word_count = len(content.split()) if content.strip() else 0
                
                # Update header stats
                self.words_label.config(text=f"{word_count:,} Words")
                self.chars_label.config(text=f"TT {char_count:,} Chars")
                
                # Update footer
                current_time = datetime.now().strftime("%I:%M %p")
                self.last_change_label.config(text=f"Last change: {current_time}")
                
        except Exception as e:
            print(f"[{self.username}] Update stats error: {e}")
    
    def _periodic_sync(self):
        """Periodic sync."""
        if self.running:
            try:
                with self.text_lock:
                    content = self.doc.get_text()
                    doc_hash = hashlib.md5(content.encode()).hexdigest()
            except:
                pass
            
            if self.running:
                self.root.after(5000, self._periodic_sync)
    
    def _on_closing(self):
        """Close application."""
        self.running = False
        self.net.close()
        self.discovery.stop()
        self.doc.persistence.stop()
        self.root.destroy()
    
    def run(self):
        """Start GUI."""
        self.root.mainloop()
