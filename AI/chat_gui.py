#!/usr/bin/env python3
"""
AI Chat Assistant - Simple GUI
Uses the business logic from chat_logic.py
"""

import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from chat_logic import AIClient, AIError, SYSTEM_MESSAGE


# ============================================
# Dark theme palette
# macOS dark mode changes default widget colours, so every colour that
# matters is set explicitly here instead of relying on defaults.
# ============================================
BG = "#1e1e1e"          # window / chat background
BG_INPUT = "#2b2b2b"    # entry + dialog text background
FG = "#e6e6e6"          # default text
FG_DIM = "#9aa0a6"      # system messages
FG_USER = "#4fc3f7"     # you
FG_AI = "#81c784"       # assistant
FG_ERROR = "#ef5350"    # errors
SELECT_BG = "#264f78"
BORDER = "#3c3c3c"


class ChatGUI:
    """Simple tkinter GUI for AI Chat Assistant."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 AI Chat Assistant")
        self.root.geometry("800x600")
        self.root.configure(bg=BG)
        
        # Initialize AI client
        self.client = AIClient(SYSTEM_MESSAGE)
        self.busy = False
        
        # Create UI
        self._apply_theme()
        self._create_ui()
    
    def _apply_theme(self):
        """Force a dark ttk theme (the native 'aqua' theme ignores colours)."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure(
            "TButton",
            background=BG_INPUT,
            foreground=FG,
            bordercolor=BORDER,
            focuscolor=BG,
            padding=6,
        )
        style.map(
            "TButton",
            background=[("active", "#3a3a3a"), ("disabled", "#262626")],
            foreground=[("disabled", FG_DIM)],
        )
        style.configure(
            "TEntry",
            fieldbackground=BG_INPUT,
            foreground=FG,
            insertcolor=FG,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
    
    def _create_ui(self):
        """Create and layout UI components."""
        # Top frame for status
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(
            top_frame, 
            text="System: Sports Expert", 
            font=("Arial", 10, "bold")
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Chat display area
        chat_frame = ttk.Frame(self.root, padding="10")
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD, 
            font=("Menlo", 12),
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            selectbackground=SELECT_BG,
            selectforeground=FG,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            borderwidth=0,
            padx=10,
            pady=10,
            state='disabled'
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Colour tags used by _print_message
        self.chat_display.tag_config("system", foreground=FG_DIM)
        self.chat_display.tag_config("user", foreground=FG_USER)
        self.chat_display.tag_config("ai", foreground=FG_AI)
        self.chat_display.tag_config("error", foreground=FG_ERROR)
        
        # Input frame
        input_frame = ttk.Frame(self.root, padding="10")
        input_frame.pack(fill=tk.X)
        
        self.message_input = ttk.Entry(input_frame, font=("Arial", 12))
        self.message_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.message_input.bind('<Return>', self._send_message)
        self.message_input.focus_set()
        
        self.send_btn = ttk.Button(input_frame, text="Send", command=self._send_message)
        self.send_btn.pack(side=tk.RIGHT)
        
        # Command buttons
        cmd_frame = ttk.Frame(self.root, padding="5")
        cmd_frame.pack(fill=tk.X)
        
        ttk.Button(cmd_frame, text="📝 Change System", 
                   command=self._change_system).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_frame, text="🧹 Clear Chat", 
                   command=self._clear_chat).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_frame, text="❌ Exit", 
                   command=self.root.quit).pack(side=tk.RIGHT, padx=5)
        
        # Add welcome message
        self._print_message("System", "AI Chat Assistant ready!")
        self._print_message("System", "Type 'quit' or 'exit' to stop.")
    
    def _print_message(self, sender: str, message: str, tag: str = None):
        """Print a message to the chat display."""
        tags = {
            "System": "system",
            "Error": "error",
            "👤 You": "user",
            "🤖 AI": "ai",
        }
        tag = tag or tags.get(sender, "")
        
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"\n[{sender}] {message}\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.configure(state='disabled')
    
    def _send_message(self, event=None):
        """Send user message to AI and get response."""
        if self.busy:
            return
        
        message = self.message_input.get().strip()
        
        if not message:
            return
        
        # Clear input
        self.message_input.delete(0, tk.END)
        
        # Print user message
        self._print_message("👤 You", message)
        
        # Process command or AI message
        if message.lower() in ['quit', 'exit']:
            self.root.quit()
        elif message.lower() == 'system':
            self._change_system()
        elif message.lower() == 'clear':
            self._clear_chat()
        else:
            self._start_stream(message)
    
    def _start_stream(self, message: str):
        """Kick off a streaming response on a worker thread."""
        self._set_busy(True)
        
        # Write the "[🤖 AI] " prefix once; chunks get appended after it.
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, "\n[🤖 AI] ", "ai")
        self.chat_display.see(tk.END)
        self.chat_display.configure(state='disabled')
        
        def worker():
            try:
                for chunk in self.client.chat_stream(message):
                    # Tkinter is not thread-safe: hop back to the main thread.
                    self.root.after(0, self._append_chunk, chunk)
            except AIError as exc:
                self.root.after(0, self._print_message, "Error", str(exc))
            except Exception as exc:  # noqa: BLE001 - surface anything unexpected
                self.root.after(0, self._print_message, "Error", f"Unexpected error: {exc}")
            finally:
                self.root.after(0, self._finish_stream)
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _append_chunk(self, chunk: str):
        """Append a streamed chunk to the current AI message (main thread only)."""
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, chunk, "ai")
        self.chat_display.see(tk.END)
        self.chat_display.configure(state='disabled')
    
    def _finish_stream(self):
        """Terminate the AI message and re-enable input."""
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, "\n")
        self.chat_display.see(tk.END)
        self.chat_display.configure(state='disabled')
        self._set_busy(False)
    
    def _set_busy(self, busy: bool):
        """Disable input while a response is in flight."""
        self.busy = busy
        state = 'disabled' if busy else 'normal'
        self.send_btn.configure(state=state)
        self.message_input.configure(state=state)
        if not busy:
            self.message_input.focus_set()
    
    def _change_system(self):
        """Open dialog to change system message."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Change System Message")
        dialog.geometry("500x400")
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter new system message:", font=("Arial", 11, "bold")).pack(
            padx=10, pady=(10, 5)
        )
        
        text_area = scrolledtext.ScrolledText(
            dialog, 
            wrap=tk.WORD, 
            height=15, 
            font=("Arial", 11),
            bg=BG_INPUT,
            fg=FG,
            insertbackground=FG,
            selectbackground=SELECT_BG,
            selectforeground=FG,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            borderwidth=0,
            padx=8,
            pady=8,
        )
        text_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        text_area.insert(tk.END, self.client.system_message.strip())
        
        def save_change():
            new_message = text_area.get("1.0", tk.END).strip()
            if new_message:
                self.client.update_system_message(new_message)
                summary = " ".join(new_message.split())[:40]
                self.status_label.config(text=f"System: {summary}...")
                dialog.destroy()
                self._print_message("System", "✅ System message updated.")
            else:
                self._print_message("Error", "❌ System message cannot be empty.")
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Save", command=save_change).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _clear_chat(self):
        """Clear chat history."""
        self.client.clear_conversation()
        self.chat_display.configure(state='normal')
        self.chat_display.delete('1.0', tk.END)
        self.chat_display.configure(state='disabled')
        self._print_message("System", "✅ Conversation cleared.")


def main():
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
