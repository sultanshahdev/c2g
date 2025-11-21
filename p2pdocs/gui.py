"""
Graphical User Interface - Tkinter-based text editor
Phase 4: Tkinter GUI
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog
import threading
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class P2PDocsEditor:
    """Main GUI window for P2PDocs"""
    
    def __init__(self, username: str, document_name: Optional[str] = None,
                 on_document_open: Optional[Callable] = None,
                 on_document_save: Optional[Callable] = None,
                 on_keystroke: Optional[Callable] = None):
        """
        Initialize the GUI
        
        Args:
            username: Username of current user
            document_name: Optional document name to open on startup
            on_document_open: Callback when document is opened
            on_document_save: Callback when document is saved
            on_keystroke: Callback when keystroke occurs
        """
        self.username = username
        self.document_name_to_open = document_name
        self.on_document_open = on_document_open
        self.on_document_save = on_document_save
        self.on_keystroke = on_keystroke
        
        # Import storage manager for P2PDocs integration
        from .storage import StorageManager
        self.storage = StorageManager()
        
        self.root = tk.Tk()
        self.root.title(f"P2PDocs - {username}")
        self.root.geometry("900x600")
        
        self.current_document = None
        self.current_peers = []
        
        self._create_menu_bar()
        self._create_toolbar()
        self._create_main_layout()
        
        logger.info(f"GUI initialized for {username}")
        
        # Open document if provided
        if self.document_name_to_open:
            self.root.after(100, self._auto_open_document)
    
    def _create_menu_bar(self):
        """Create menu bar with File, Edit, View menus"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self._new_document)
        file_menu.add_command(label="Open", command=self._open_document)
        file_menu.add_command(label="Save", command=self._save_document)
        file_menu.add_command(label="Save As", command=self._save_as_document)
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
        
        tk.Button(toolbar, text="New", command=self._new_document).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Open", command=self._open_document).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Save", command=self._save_document).pack(side=tk.LEFT, padx=2)
        
        tk.Label(toolbar, text=" | Document:").pack(side=tk.LEFT, padx=5)
        self.doc_label = tk.Label(toolbar, text="[New Document]", bg="white", width=40)
        self.doc_label.pack(side=tk.LEFT, padx=2)
        
        tk.Label(toolbar, text="Lock Status:").pack(side=tk.LEFT, padx=5)
        self.lock_status = tk.Label(toolbar, text="⭘ Unlocked", fg="green", font=("Arial", 10, "bold"))
        self.lock_status.pack(side=tk.LEFT, padx=2)
    
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
        """Handle keystroke event"""
        if self.on_keystroke:
            self.on_keystroke(event)
    
    def _new_document(self):
        """Create a new document"""
        self.text_area.delete("1.0", tk.END)
        self.current_document = None
        self.doc_label.config(text="[New Document]")
        self.update_status("New document created")
    
    def _open_document(self):
        """Open a P2PDocs document"""
        # Get list of available documents
        docs = self.storage.list_documents()
        if not docs:
            messagebox.showinfo("Info", "No documents available")
            return
        
        # Create a simple dialog to select document
        dialog = tk.simpledialog.askstring(
            "Open Document", 
            f"Available documents:\n{', '.join(docs)}\n\nEnter document name:"
        )
        
        if dialog:
            doc_name = dialog.strip()
            success, content = self.storage.read_document(doc_name)
            if success:
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", content)
                self.current_document = doc_name
                self.doc_label.config(text=doc_name)
                self.root.title(f"P2PDocs - {self.username} - {doc_name}")
                self.add_recent_document(doc_name)
                self.update_status(f"Opened: {doc_name}")
                
                if self.on_document_open:
                    self.on_document_open(doc_name)
            else:
                messagebox.showerror("Error", f"Failed to open document: {content}")
    
    def _save_document(self):
        """Save the current document to P2PDocs storage"""
        if not self.current_document:
            self._save_as_document()
            return
        
        try:
            content = self.text_area.get("1.0", tk.END)
            
            # Save to P2PDocs storage
            success, message = self.storage.update_document(self.current_document, content)
            
            if success:
                self.update_status(f"Saved: {self.current_document}")
                
                if self.on_document_save:
                    self.on_document_save(self.current_document, content)
            else:
                messagebox.showerror("Error", f"Failed to save: {message}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save document: {str(e)}")
    
    def _save_as_document(self):
        """Save document with new name to P2PDocs storage"""
        # Ask for document name instead of file path
        dialog = tk.simpledialog.askstring("Save As", "Enter document name:")
        if dialog:
            doc_name = dialog.strip()
            if not doc_name:
                messagebox.showwarning("Warning", "Document name cannot be empty")
                return
            
            try:
                content = self.text_area.get("1.0", tk.END)
                success, message = self.storage.create_document(doc_name, self.username, content)
                
                if success:
                    self.current_document = doc_name
                    self.doc_label.config(text=doc_name)
                    self.root.title(f"P2PDocs - {self.username} - {doc_name}")
                    self.update_status(f"Saved: {doc_name}")
                    self.add_recent_document(doc_name)
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
    
    def _auto_open_document(self):
        """Auto-open document if specified on startup"""
        if not self.document_name_to_open:
            return
        
        try:
            from .storage import StorageManager
            storage = StorageManager()
            
            success, content = storage.read_document(self.document_name_to_open)
            if success:
                self.set_document_content(content)
                self.current_document = self.document_name_to_open
                self.root.title(f"P2PDocs - {self.username} - {self.document_name_to_open}")
                self.add_recent_document(self.document_name_to_open)
                logger.info(f"Auto-opened document: {self.document_name_to_open}")
            else:
                messagebox.showerror("Error", f"Could not open document: {content}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open document: {e}")
            logger.error(f"Auto-open failed: {e}")
    
    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()
    
    def close(self):
        """Close the GUI"""
        self.root.quit()
