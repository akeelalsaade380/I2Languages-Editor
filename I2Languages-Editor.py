import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import re

# Library for drag and drop functionality
try:
    import tkinterdnd2
except ImportError:
    tkinterdnd2 = None

class I2Editor(tkinterdnd2.TkinterDnD.Tk if tkinterdnd2 else tk.Tk):
    def __init__(self):
        super().__init__()
        
        # --- Main Window Configuration ---
        self.title("Universal I2 Editor (Raw Code Mode) - By MrGamesKingPro")
        self.geometry("1200x750")

        # --- State Variables ---
        self.data = None  
        self.current_filepath = None  
        self.term_to_tree_item = {}  
        self.term_to_original_index = {} 
        self.terms_list_ref = None  
        self.file_mode = "standard" # 'standard' for I2, 'task' for DailyTaskInfo
        self.currently_editing_term_key = None
        self.language_names = []

        self._create_widgets()
        
        # Register for Drag and Drop if library is present
        if tkinterdnd2:
            self.drop_target_register('DND_FILES')
            self.dnd_bind('<<Drop>>', self.on_drop)

    def _create_widgets(self):
        # --- File Menu ---
        self.menu = tk.Menu(self)
        self.config(menu=self.menu)
        
        file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open...", command=self.open_file_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Export to TXT", command=self.export_to_txt)
        file_menu.add_command(label="Import from TXT", command=self.import_from_txt)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # --- Toolbar (Language and Search) ---
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Select Language:").pack(side=tk.LEFT, padx=(0, 5))
        self.language_var = tk.StringVar()
        self.language_combo = ttk.Combobox(top_frame, textvariable=self.language_var, state="disabled")
        self.language_combo.pack(side=tk.LEFT, padx=5)
        self.language_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        
        search_frame = ttk.Frame(top_frame, padding="5")
        search_frame.pack(side=tk.RIGHT)
        self.search_entry = ttk.Entry(search_frame, width=20)
        self.search_entry.grid(row=0, column=0, padx=5)
        ttk.Button(search_frame, text="Find", command=self.find_next).grid(row=0, column=1, padx=2)
        self.replace_entry = ttk.Entry(search_frame, width=20)
        self.replace_entry.grid(row=1, column=0, padx=5)
        ttk.Button(search_frame, text="Replace All", command=self.replace_all).grid(row=1, column=1, padx=2)

        # --- Main Workspace ---
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        # Table Section
        tree_frame = ttk.Frame(main_pane)
        main_pane.add(tree_frame, weight=3)
        cols = ("#", "term", "text")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        self.tree.heading("#", text="No.")
        self.tree.heading("term", text="Term Key")
        self.tree.heading("text", text="Preview (Codes Visible)")
        self.tree.column("#", width=50, anchor="center")
        self.tree.column("term", width=250)
        self.tree.column("text", width=700)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Editor Section
        editor_frame = ttk.LabelFrame(main_pane, text="Text Editor (Raw Code Mode: \\n is text)", padding="10")
        main_pane.add(editor_frame, weight=1)
        self.editor_text = tk.Text(editor_frame, wrap="none", height=6, undo=True)
        self.editor_text.pack(expand=True, fill="both", side="left")
        self.apply_btn = ttk.Button(editor_frame, text="Apply Changes", command=self.save_from_editor, state="disabled")
        self.apply_btn.pack(padx=10, anchor="n")

        self.status_bar = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Key Bindings
        self.bind("<Control-o>", lambda e: self.open_file_dialog())
        self.bind("<Control-s>", lambda e: self.save_file())
        self.bind("<Control-S>", lambda e: self.save_file_as())

    # --- Text Code Handling ---
    def _escape_text(self, text):
        """Converts real newlines to literal '\n' and '\r' strings."""
        if text is None: return ""
        return str(text).replace("\r", "\\r").replace("\n", "\\n")

    def _unescape_text(self, text):
        """Converts literal '\n' and '\r' strings back to actual newline characters."""
        return text.replace("\\r", "\r").replace("\\n", "\n")

    # --- Loading and Detection ---
    def load_file_logic(self, filepath):
        """Reads JSON and detects if it is a standard I2 file, Blasphemous format, or DailyTask file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            self.terms_list_ref = None
            
            # --- تحديد مسار مصفوفة النصوص بناءً على هيكل الملف ---
            if 'mSource' in self.data and 'mTerms' in self.data['mSource']:
                self.terms_list_ref = self.data['mSource']['mTerms'].get('Array')
                self.file_mode = "standard"
            elif 'mTerms' in self.data:  # دعم ملفات Blasphemous (mTerms في الجذر)
                self.terms_list_ref = self.data['mTerms'].get('Array')
                self.file_mode = "standard"
            elif 'dailyTaskInfoList' in self.data:
                self.terms_list_ref = self.data['dailyTaskInfoList'].get('Array')
                self.file_mode = "task"
            
            if self.terms_list_ref is None:
                raise ValueError("لم يتم التعرف على بنية الملف. (Format not recognized)")

            self.current_filepath = filepath
            self.detect_languages()
            self.populate_treeview()
            self.status_bar.config(text=f"Loaded ({self.file_mode}): {filepath}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file:\n{str(e)}")

    def detect_languages(self):
        """Finds how many languages are in the first entry."""
        if not self.terms_list_ref: return
        try:
            if self.file_mode == "standard":
                langs = self.terms_list_ref[0]['Languages']['Array']
            else:
                langs = self.terms_list_ref[0]['intro']['values']['Array']
            self.language_names = [f"Language {i}" for i in range(len(langs))]
            self.language_combo.config(values=self.language_names, state="readonly")
            self.language_var.set(self.language_names[0])
        except Exception as e: 
            print(f"Warning in detect_languages: {e}")

    def populate_treeview(self):
        """Clears and fills the table using escaped text (codes visible)."""
        if not self.data: return
        self.tree.delete(*self.tree.get_children())
        self.term_to_tree_item.clear()
        self.term_to_original_index.clear()
        
        lang_idx = self._get_selected_language_index()
        for i, entry in enumerate(self.terms_list_ref):
            if self.file_mode == "standard":
                key = entry.get('Term', f"Row_{i}")
                raw_text = entry['Languages']['Array'][lang_idx]
            else:
                key = f"Task_Type_{entry.get('type', i)}"
                raw_text = entry['intro']['values']['Array'][lang_idx]
                
            display_text = self._escape_text(raw_text)
            item_id = self.tree.insert("", "end", values=(i + 1, key, display_text))
            self.term_to_tree_item[key] = item_id
            self.term_to_original_index[key] = i

    def _get_selected_language_index(self):
        try: return int(self.language_var.get().split(' ')[1])
        except: return 0

    # --- Editor Functions ---
    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        item_id = selected[0]
        term_key = self.tree.item(item_id, "values")[1]
        lang_idx = self._get_selected_language_index()
        orig_idx = self.term_to_original_index.get(term_key)
        
        if self.file_mode == "standard":
            raw = self.terms_list_ref[orig_idx]['Languages']['Array'][lang_idx]
        else:
            raw = self.terms_list_ref[orig_idx]['intro']['values']['Array'][lang_idx]
            
        self.editor_text.config(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", self._escape_text(raw))
        self.apply_btn.config(state="normal")
        self.currently_editing_term_key = term_key

    def save_from_editor(self):
        """Takes user input from UI and converts \n back to newline characters for JSON."""
        if not self.currently_editing_term_key: return
        ui_text = self.editor_text.get("1.0", "end-1c")
        self.update_data_and_tree(self.currently_editing_term_key, self._unescape_text(ui_text))

    def update_data_and_tree(self, term_key, real_newline_text):
        """Updates internal dictionary and the table preview."""
        lang_idx = self._get_selected_language_index()
        idx = self.term_to_original_index[term_key]
        if self.file_mode == "standard":
            self.terms_list_ref[idx]['Languages']['Array'][lang_idx] = real_newline_text
        else:
            self.terms_list_ref[idx]['intro']['values']['Array'][lang_idx] = real_newline_text

        item_id = self.term_to_tree_item[term_key]
        vals = list(self.tree.item(item_id, "values"))
        vals[2] = self._escape_text(real_newline_text)
        self.tree.item(item_id, values=tuple(vals))

    # --- Saving Functions ---
    def save_file(self):
        if self.current_filepath:
            self._write_to_file(self.current_filepath)
        else:
            self.save_file_as()

    def save_file_as(self):
        """Opens a dialog to save the JSON to a new location."""
        if not self.data: return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.current_filepath = path
            self._write_to_file(path)

    def _write_to_file(self, path):
        """Core logic to write the JSON data to disk."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Success", f"File saved to:\n{path}")
            self.status_bar.config(text=f"Last saved: {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # --- Export and Import ---
    def export_to_txt(self):
        """Saves current language items into a TXT file without extra quotes, keeping codes like \n."""
        if not self.data: return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if not path: return
        lang_idx = self._get_selected_language_index()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for item_id in self.tree.get_children():
                    key = self.tree.item(item_id, "values")[1]
                    idx = self.term_to_original_index[key]
                    if self.file_mode == "standard":
                        raw = self.terms_list_ref[idx]['Languages']['Array'][lang_idx]
                    else:
                        raw = self.terms_list_ref[idx]['intro']['values']['Array'][lang_idx]
                    
                    escaped_text = self._escape_text(raw)
                    f.write(f'{escaped_text}\n')
                    
            messagebox.showinfo("Export", "TXT file exported successfully (Clean text without quotes).")
        except Exception as e: 
            messagebox.showerror("Export Error", str(e))

    def import_from_txt(self):
        """Reads a TXT file and injects the text back."""
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if not path: return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            tree_items = self.tree.get_children()
            
            if len(lines) != len(tree_items):
                messagebox.showerror("Import Error", f"Line count mismatch!\nTXT file has {len(lines)} lines, but the JSON requires {len(tree_items)} lines.\nImport aborted to prevent data corruption.")
                return

            for item_id, line in zip(tree_items, lines):
                processed = line.rstrip('\n')
                term_key = self.tree.item(item_id, "values")[1]
                self.update_data_and_tree(term_key, self._unescape_text(processed))
                
            messagebox.showinfo("Import", "Text imported successfully! They will have quotes when saved to JSON.")
        except Exception as e: 
            messagebox.showerror("Import Error", str(e))

    # --- Utilities ---
    def find_next(self):
        query = self.search_entry.get().lower()
        if not query: return
        items = self.tree.get_children()
        start = self.tree.focus()
        idx = (items.index(start) + 1) if start in items else 0
        for i in range(len(items)):
            target = items[(idx + i) % len(items)]
            if query in self.tree.item(target, "values")[2].lower():
                self.tree.selection_set(target)
                self.tree.focus(target)
                self.tree.see(target)
                return

    def replace_all(self):
        q, r = self.search_entry.get(), self.replace_entry.get()
        if not q or not messagebox.askyesno("Confirm", "Replace all occurrences?"): return
        lang_idx = self._get_selected_language_index()
        for key, idx in self.term_to_original_index.items():
            if self.file_mode == "standard":
                old = self.terms_list_ref[idx]['Languages']['Array'][lang_idx]
            else:
                old = self.terms_list_ref[idx]['intro']['values']['Array'][lang_idx]
            new = re.sub(re.escape(q), r, str(old), flags=re.IGNORECASE)
            self.update_data_and_tree(key, new)

    def on_language_change(self, e): self.populate_treeview()
    def on_drop(self, e): self.load_file_logic(self.tk.splitlist(e.data)[0].strip('{}'))
    def open_file_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path: self.load_file_logic(path)

if __name__ == "__main__":
    app = I2Editor()
    app.mainloop()
