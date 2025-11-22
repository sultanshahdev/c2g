"""
Graphical User Interface - Tkinter-based text editor
Phase 4: Tkinter GUI
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog
import threading
from typing import Optional, Callable, Dict
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)


class P2PDocsEditor:
    """Main GUI window for P2PDocs"""
    
    def __init__(self, username: str, document_name: Optional[str] = None,
                 on_document_open: Optional[Callable] = None,
                 on_document_save: Optional[Callable] = None,
                 on_keystroke: Optional[Callable] = None,
                 network_manager = None):
        """
        Initialize the GUI
        
        Args:
            username: Username of current user
            document_name: Optional document name to open on startup
            on_document_open: Callback when document is opened
            on_document_save: Callback when document is saved
            on_keystroke: Callback when keystroke occurs
            network_manager: Optional NetworkManager for real-time sync
        """
        self.username = username
        self.document_name_to_open = document_name
        self.on_document_open = on_document_open
        self.on_document_save = on_document_save
        self.on_keystroke = on_keystroke
        self.network_manager = network_manager
        
        # Import storage manager for P2PDocs integration
        from .storage import StorageManager
        self.storage = StorageManager()
        
        self.root = tk.Tk()
        self.root.title(f"P2PDocs - {username}")
        self.root.geometry("900x600")
        
        # Single shared document mode
        self.shared_doc_name = "shared_document.txt"
        self.current_document = self.shared_doc_name  # Always use shared document
        self.current_peers = []
        self.peer_colors: Dict[str, str] = {}  # Maps peer username to color
        self.auto_sync_enabled = True  # Auto-sync changes to network
        
        # Auto-save state
        self.last_saved_content = ""  # Track last saved content for auto-save
        self.auto_save_timer = None  # Timer for auto-save
        self.auto_save_interval = 3000  # Auto-save every 3 seconds (milliseconds)
        self.has_unsaved_changes = False  # Flag for unsaved changes
        
        # Color palette for peers
        self.color_palette = [
            "#FF6B6B",  # Red
            "#4ECDC4",  # Teal
            "#45B7D1",  # Blue
            "#FFA07A",  # Light Salmon
            "#98D8C8",  # Mint
            "#F7DC6F",  # Yellow
            "#BB8FCE",  # Purple
            "#85C1E2",  # Light Blue
            "#F8B88B",  # Peach
            "#82E0AA",  # Green
        ]
        self.color_index = 0
        
        # Handle window close event (X button or Alt+F4)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        
        self._create_menu_bar()
        self._create_toolbar()
        self._create_main_layout()
        
        logger.info(f"GUI initialized for {username}")
        
        # Create new blank document and register for peer updates
        self._create_new_blank_document()
        self._register_network_callbacks()
    
    def _create_menu_bar(self):
        """Create menu bar with File, Edit, View menus"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu - Simplified for single shared document
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save", command=self._save_document)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._undo)
        edit_menu.add_command(label="Redo", command=self._redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self._cut)
        edit_menu.add_command(label="Copy", command=self._copy)
        edit_menu.add_command(label="Paste", command=self._paste)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=self._select_all)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Increase Font", command=self._increase_font)
        view_menu.add_command(label="Decrease Font", command=self._decrease_font)
        view_menu.add_command(label="Reset Font", command=self._reset_font)
    
    def _create_toolbar(self):
        """Create toolbar with quick action buttons"""
        toolbar = tk.Frame(self.root, bg="lightgray", height=40)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Simplified toolbar - only Save button for shared document
        tk.Button(toolbar, text="Save", command=self._save_document).pack(side=tk.LEFT, padx=2)
        
        tk.Label(toolbar, text=" | Shared Document:").pack(side=tk.LEFT, padx=5)
        self.doc_label = tk.Label(toolbar, text=self.shared_doc_name, bg="white", width=40)
        self.doc_label.pack(side=tk.LEFT, padx=2)
    
    def _create_main_layout(self):
        """Create main content area with text editor and sidebar"""
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left side - Text editor
        editor_frame = tk.Frame(main_frame)
        editor_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Editor label
        tk.Label(editor_frame, text="Document Content:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        # Text area with scrollbar
        self.text_area = scrolledtext.ScrolledText(
            editor_frame, 
            wrap=tk.WORD, 
            font=("Courier New", 11),
            undo=True,
            maxundo=-1
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # Bind keystroke event
        self.text_area.bind("<KeyRelease>", self._on_keystroke)
        
        # Right side - Sidebar with peer list
        sidebar_frame = tk.Frame(main_frame, width=200, bg="lightblue")
        sidebar_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        
        tk.Label(sidebar_frame, text="Connected Peers", font=("Arial", 10, "bold"), bg="lightblue").pack(anchor=tk.W, padx=5, pady=5)
        
        # Peers listbox
        self.peers_listbox = tk.Listbox(sidebar_frame, height=15, width=25)
        self.peers_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Peer count
        tk.Label(sidebar_frame, text="Recent Documents", font=("Arial", 10, "bold"), bg="lightblue").pack(anchor=tk.W, padx=5, pady=5)
        
        # Recent docs listbox
        self.recent_listbox = tk.Listbox(sidebar_frame, height=8, width=25)
        self.recent_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status bar
        status_frame = tk.Frame(self.root, bg="gray", height=20)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = tk.Label(
            status_frame, 
            text="Ready", 
            bg="gray", 
            fg="white",
            anchor=tk.W,
            padx=10
        )
        self.status_label.pack(fill=tk.X)
    
    def _on_keystroke(self, event):
        """Handle keystroke event - trigger auto-save"""
        self.has_unsaved_changes = True
        
        # Reset auto-save timer
        if self.auto_save_timer:
            self.root.after_cancel(self.auto_save_timer)
        
        # Schedule auto-save
        if self.current_document:
            self.auto_save_timer = self.root.after(self.auto_save_interval, self._auto_save)
        
        if self.on_keystroke:
            self.on_keystroke(event)
    
    def _create_new_blank_document(self):
        """Load the shared document on startup if it exists"""
        try:
            # Try to load existing shared document
            success, content = self.storage.read_document(self.shared_doc_name)
            
            if success:
                # Document exists, load it
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", content)
                self.last_saved_content = content
                logger.info(f"Loaded shared document: {content[:50] if content else '(empty)'}...")
            else:
                # Document doesn't exist yet - start with blank
                self.text_area.delete("1.0", tk.END)
                self.last_saved_content = ""
                logger.info("Starting with blank document (waiting for peers or first save)")
        except Exception as e:
            logger.error(f"Error loading shared document: {e}")
            self.text_area.delete("1.0", tk.END)
            self.last_saved_content = ""
        
        self.has_unsaved_changes = False
        self.doc_label.config(text=self.shared_doc_name)
        self.root.title(f"P2PDocs - {self.username}")
        self.update_status("Ready - type and auto-sync with peers")
    
    def _register_network_callbacks(self):
        """Register callbacks with network manager for peer updates"""
        if not self.network_manager:
            return
        
        # Callback when a peer joins
        def on_peer_joined(peer_username):
            logger.info(f"Peer {peer_username} joined")
            self.root.after(0, self._update_peers_from_network)
        
        # Callback when peers change
        def on_peer_updated():
            logger.info("Peer list updated")
            self.root.after(0, self._update_peers_from_network)
        
        # Callback when shared document is updated by remote peer
        def on_document_updated(doc_name, sender, content=None):
            logger.info(f"Document '{doc_name}' updated by {sender}")
            if doc_name == self.shared_doc_name:
                # Shared document updated - refresh display
                self.root.after(0, self._on_remote_document_update, doc_name, sender, content)
        
        self.network_manager.register_callback("on_peer_joined", on_peer_joined)
        self.network_manager.register_callback("on_peer_updated", on_peer_updated)
        self.network_manager.register_callback("on_document_updated", on_document_updated)
        
        # Initial peers list update
        self.root.after(500, self._update_peers_from_network)
    
    def _update_peers_from_network(self):
        """Update peer list from network manager"""
        if not self.network_manager:
            return
        
        try:
            peers = self.network_manager.get_discovered_peers()
            connected = self.network_manager.get_connected_peers()
            connected_usernames = {p.username for p in connected}
            
            self.peers_listbox.delete(0, tk.END)
            self.current_peers = []
            
            for peer in peers:
                if peer.username == self.username:
                    continue
                
                # Assign color if new peer
                if peer.username not in self.peer_colors:
                    color = self.color_palette[self.color_index % len(self.color_palette)]
                    self.peer_colors[peer.username] = color
                    self.color_index += 1
                
                # Format: peer_name (connected/disconnected)
                status = "🟢 " if peer.username in connected_usernames else "🔴 "
                display_name = f"{status}{peer.username}"
                self.peers_listbox.insert(tk.END, display_name)
                
                self.current_peers.append(peer)
                logger.debug(f"Added peer {peer.username} with color {self.peer_colors[peer.username]}")
        
        except Exception as e:
            logger.error(f"Error updating peers: {e}")
    
    def get_peer_color(self, peer_username: str) -> str:
        """Get assigned color for a peer"""
        return self.peer_colors.get(peer_username, "#888888")
    
    def _on_remote_document_update(self, doc_name: str, sender: str, content: str = None):
        """Handle remote document update - show merge dialog or auto-update"""
        if doc_name != self.current_document:
            return
        
        try:
            # Use provided content if available, otherwise read from storage
            if content is None:
                success, updated_content = self.storage.read_document(doc_name)
                if not success:
                    logger.warning(f"Could not read updated document: {updated_content}")
                    self.update_status(f"Document updated by {sender}")
                    return
            else:
                updated_content = content
            
            current_content = self.text_area.get("1.0", tk.END)
            
            # Check if content is different
            if current_content == updated_content:
                logger.info(f"Remote update to '{doc_name}' is identical to local")
                self.update_status(f"'{doc_name}' synced with {sender}")
                return
            
            # If local content is empty or unchanged, auto-accept remote
            if not self.has_unsaved_changes or current_content.strip() == "":
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", updated_content)
                self.last_saved_content = updated_content
                self.update_status(f"Auto-updated from {sender}")
                logger.info(f"Auto-accepted remote update to '{doc_name}' from {sender}")
                return
            
            # Show merge dialog for conflicting changes
            peer_color = self.get_peer_color(sender)
            response = messagebox.askyesnocancel(
                "Document Updated",
                f"Peer '{sender}' has updated this document.\n\n"
                f"Do you want to accept their changes?\n\n"
                f"Yes = Accept their version\n"
                f"No = Keep your changes\n"
                f"Cancel = Show diff",
                icon=messagebox.INFO
            )
            
            if response is True:
                # Accept remote changes
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", updated_content)
                self.last_saved_content = updated_content
                self.update_status(f"Accepted changes from {sender}")
                logger.info(f"Accepted remote update to '{doc_name}' from {sender}")
            elif response is False:
                # Keep local changes - no action needed
                self.update_status(f"Kept local changes (rejected {sender}'s update)")
                logger.info(f"Rejected remote update to '{doc_name}' from {sender}")
            # else: Cancel - user wants to see diff (future enhancement)
        
        except Exception as e:
            logger.error(f"Error handling remote update: {e}")
            messagebox.showerror("Error", f"Error processing remote update: {str(e)}")
    
    def _auto_save(self):
        """Auto-save document if changes detected - create on first save, update after"""
        if not self.current_document or not self.has_unsaved_changes:
            return
        
        try:
            current_content = self.text_area.get("1.0", tk.END)
            
            # Only save if content changed since last save
            if current_content != self.last_saved_content:
                docs = self.storage.list_documents()
                
                if self.shared_doc_name not in docs:
                    # First save - create document
                    success, message = self.storage.create_document(self.shared_doc_name, self.username, current_content)
                else:
                    # Update existing
                    success, message = self.storage.update_document(self.current_document, current_content)
                
                if success:
                    self.last_saved_content = current_content
                    self.has_unsaved_changes = False
                    self.update_status(f"Auto-saved")
                    
                    # Broadcast to network peers if connected
                    if self.network_manager and self.auto_sync_enabled:
                        self.network_manager.broadcast_document_update(
                            self.current_document,
                            current_content
                        )
                    
                    logger.debug(f"Auto-saved document: {self.current_document}")
        
        except Exception as e:
            logger.error(f"Auto-save error: {e}")
    

    def _save_document(self):
        """Manually save - try update first, create if doesn't exist"""
        try:
            content = self.text_area.get("1.0", tk.END)
            
            # Try to update first
            success, message = self.storage.update_document(self.shared_doc_name, content)
            
            # If update failed because doc doesn't exist, create it
            if not success and "not found" in message.lower():
                success, message = self.storage.create_document(self.shared_doc_name, self.username, content)
            
            if success:
                self.last_saved_content = content
                self.has_unsaved_changes = False
                self.update_status(f"Saved and shared")
                
                # Broadcast to network peers if connected
                if self.network_manager and self.auto_sync_enabled:
                    self.network_manager.broadcast_document_update(
                        self.shared_doc_name,
                        content
                    )
                
                if self.on_document_save:
                    self.on_document_save(self.shared_doc_name, content)
            else:
                messagebox.showerror("Error", f"Failed to save: {message}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save document: {str(e)}")

    
    def _undo(self):
        """Undo last action"""
        try:
            self.text_area.edit_undo()
        except tk.TclError:
            pass
    
    def _redo(self):
        """Redo last action"""
        try:
            self.text_area.edit_redo()
        except tk.TclError:
            pass
    
    def _cut(self):
        """Cut selected text"""
        try:
            text = self.text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.text_area.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            messagebox.showinfo("Info", "No text selected")
    
    def _copy(self):
        """Copy selected text"""
        try:
            text = self.text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.update_status("Copied to clipboard")
        except tk.TclError:
            messagebox.showinfo("Info", "No text selected")
    
    def _paste(self):
        """Paste text from clipboard"""
        try:
            text = self.root.clipboard_get()
            self.text_area.insert(tk.INSERT, text)
            self.update_status("Pasted from clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to paste: {str(e)}")
    
    def _select_all(self):
        """Select all text"""
        self.text_area.tag_add(tk.SEL, "1.0", tk.END)
        self.text_area.mark_set(tk.INSERT, "1.0")
        self.text_area.see(tk.INSERT)
    
    def _increase_font(self):
        """Increase font size"""
        current_font = self.text_area.cget("font")
        # Simple font size increase
        self.text_area.configure(font=("Courier New", 12))
    
    def _decrease_font(self):
        """Decrease font size"""
        self.text_area.configure(font=("Courier New", 10))
    
    def _reset_font(self):
        """Reset font to default"""
        self.text_area.configure(font=("Courier New", 11))
    
    def update_status(self, message: str):
        """Update status bar"""
        self.status_label.config(text=message)
        self.root.update()
    
    def update_lock_status(self, locked: bool, owner: str = ""):
        """Update lock status display"""
        if locked:
            status = f"🔒 Locked by {owner}"
            color = "red" if owner != self.username else "blue"
        else:
            status = "⭘ Unlocked"
            color = "green"
        
        self.lock_status.config(text=status, fg=color)
    
    def update_peers(self, peers: list):
        """Update peer list display"""
        self.peers_listbox.delete(0, tk.END)
        self.current_peers = peers
        
        for peer in peers:
            display_name = f"{peer.username} ({peer.host}:{peer.port})"
            self.peers_listbox.insert(tk.END, display_name)
    
    def add_recent_document(self, doc_name: str):
        """Add document to recent list"""
        self.recent_listbox.insert(0, doc_name)
        # Keep only last 10
        if self.recent_listbox.size() > 10:
            self.recent_listbox.delete(10)
    
    def get_document_content(self) -> str:
        """Get current document content"""
        return self.text_area.get("1.0", tk.END)
    
    def set_document_content(self, content: str):
        """Set document content"""
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", content)
    

    def run(self):
        """Start the GUI event loop and cleanup on exit"""
        try:
            self.root.mainloop()
        finally:
            # Cleanup network manager when GUI exits (any way it exits)
            if self.network_manager:
                logger.info("GUI closing. Stopping network manager...")
                self.network_manager.stop()
                logger.info("Network manager stopped.")
    
    def close(self):
        """Close the GUI window - called by close button or File->Exit"""
        # Cancel auto-save timer
        if self.auto_save_timer:
            self.root.after_cancel(self.auto_save_timer)
        
        self.root.destroy()  # Destroy window triggers mainloop exit
