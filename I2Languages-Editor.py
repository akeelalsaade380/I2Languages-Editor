import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import re
# To use the drag-and-drop feature, this library must be installed:
# pip install tkinterdnd2
try:
    import tkinterdnd2
except ImportError:
    # Fallback if tkinterdnd2 is not installed
    tkinterdnd2 = None

class I2Editor(tkinterdnd2.TkinterDnD.Tk if tkinterdnd2 else tk.Tk):
    def __init__(self):
        super().__init__()
        
        # --- Main window settings ---
        self.title("Universal I2 & Task Editor By MrGamesKingPro")
        self.geometry("1100x700")

        # --- Application state variables ---
        self.data = None  
        self.current_filepath = None  
        self.term_to_tree_item = {}  
        self.term_to_original_index = {} 
        self.terms_list_ref = None  
        
        # Mode detection: 'standard' for I2, 'task' for the new format
        self.file_mode = "standard" 
        
        self.currently_editing_term_key = None
        self.language_names = []
        self.detected_english_index = None

        # --- Build UI ---
        self._create_widgets()
        
        if tkinterdnd2:
            self.drop_target_register('DND_FILES')
            self.dnd_bind('<<Drop>>', self.on_drop)

    def _create_widgets(self):
        self.menu = tk.Menu(self)
        self.config(menu=self.menu)
        
        file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open...", command=self.open_file_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Export to TXT...", command=self.export_to_txt)
        file_menu.add_command(label="Import from TXT...", command=self.import_from_txt)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Select Language:").pack(side=tk.LEFT, padx=(0, 5))
        self.language_var = tk.StringVar()
        self.language_combo = ttk.Combobox(top_frame, textvariable=self.language_var, state="disabled")
        self.language_combo.pack(side=tk.LEFT, padx=5)
        self.language_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        
        search_frame = ttk.Frame(top_frame, padding="10")
        search_frame.pack(side=tk.RIGHT)
        
        ttk.Label(search_frame, text="Find:").grid(row=0, column=0, padx=5, pady=2, sticky='w')
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(search_frame, text="Find Next", command=self.find_next).grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(search_frame, text="Replace:").grid(row=1, column=0, padx=5, pady=2, sticky='w')
        self.replace_entry = ttk.Entry(search_frame)
        self.replace_entry.grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(search_frame, text="Replace", command=self.replace_selected).grid(row=1, column=2, padx=5, pady=2)
        ttk.Button(search_frame, text="Replace All", command=self.replace_all).grid(row=1, column=3, padx=5, pady=2)

        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        tree_frame = ttk.Frame(main_pane, padding=(0, 10, 0, 0))
        main_pane.add(tree_frame, weight=3) 
        
        columns = ("#", "term", "text")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.tree.heading("#", text="No.")
        self.tree.heading("term", text="Term / Type")
        self.tree.heading("text", text="Translation Preview")
        
        self.tree.column("#", width=50, anchor='center')
        self.tree.column("term", width=250)
        self.tree.column("text", width=700)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        editor_frame = ttk.LabelFrame(main_pane, text="Full Text Editor", padding="10")
        main_pane.add(editor_frame, weight=1)

        self.editor_text = tk.Text(editor_frame, wrap="word", height=8, undo=True)
        self.editor_text.pack(expand=True, fill="both", side="left", padx=(0, 10))
        self.editor_text.config(state="disabled")

        self.save_button = ttk.Button(editor_frame, text="Save Changes", command=self.save_from_editor, state="disabled")
        self.save_button.pack(pady=10, anchor="n")

        self.status_bar = ttk.Label(self, text="Open a JSON file (I2 or Task Info) to begin.", relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.bind("<Control-o>", lambda e: self.open_file_dialog())
        self.bind("<Control-s>", lambda e: self.save_file())

    def on_tree_select(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            self._clear_editor()
            return

        item_id = selected_items[0]
        term_key = self.tree.item(item_id, "values")[1]
        
        lang_index = self._get_selected_language_index()
        original_index = self.term_to_original_index.get(term_key)

        if lang_index is None or original_index is None: return

        try:
            if self.file_mode == "standard":
                full_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]
            else: # Task mode
                full_text = self.terms_list_ref[original_index]['intro']['values']['Array'][lang_index]
        except (KeyError, IndexError):
            full_text = ""

        self.editor_text.config(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", full_text)
        self.save_button.config(state="normal")
        self.currently_editing_term_key = term_key

    def _clear_editor(self):
        self.editor_text.config(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.config(state="disabled")
        self.save_button.config(state="disabled")
        self.currently_editing_term_key = None

    def load_file_logic(self, filepath):
        """Detects structure and loads file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            # 1. Try Standard I2
            self.terms_list_ref = None
            if 'mSource' in self.data and 'mTerms' in self.data['mSource']:
                self.terms_list_ref = self.data['mSource']['mTerms'].get('Array')
                self.file_mode = "standard"
            # 2. Try Daily Task Format
            elif 'dailyTaskInfoList' in self.data:
                self.terms_list_ref = self.data['dailyTaskInfoList'].get('Array')
                self.file_mode = "task"
            
            if self.terms_list_ref is None:
                raise ValueError("Unsupported JSON structure.")

            self.current_filepath = filepath
            self.detect_languages()
            self.populate_treeview()
            self.status_bar.config(text=f"Loaded [{self.file_mode}] mode: {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def detect_languages(self):
        if not self.terms_list_ref: return
        
        # Determine number of translations from first item
        try:
            if self.file_mode == "standard":
                langs = self.terms_list_ref[0].get('Languages', {}).get('Array', [])
            else:
                langs = self.terms_list_ref[0].get('intro', {}).get('values', {}).get('Array', [])
            
            num_languages = len(langs)
            self.language_names = [f"Language {i}" for i in range(num_languages)]
            self.language_combo.config(values=self.language_names, state="readonly")
            self.language_var.set(self.language_names[0])
        except:
            self.status_bar.config(text="Could not detect languages.")

    def populate_treeview(self):
        if not self.data: return
        self.tree.delete(*self.tree.get_children())
        self.term_to_tree_item.clear()
        self.term_to_original_index.clear()
        self._clear_editor()
        
        lang_index = self._get_selected_language_index()
        if lang_index is None: return

        for i, term_data in enumerate(self.terms_list_ref):
            # Define a unique key for the tree
            if self.file_mode == "standard":
                term_key = term_data.get('Term', f"ID_{i}")
                translations = term_data.get('Languages', {}).get('Array', [])
            else:
                term_key = f"Task_Type_{term_data.get('type', i)}"
                translations = term_data.get('intro', {}).get('values', {}).get('Array', [])

            try:
                full_translation = translations[lang_index]
            except IndexError:
                full_translation = ""
            
            display_text = full_translation.replace('\n', ' ').strip()[:100]
            item_id = self.tree.insert("", "end", values=(i + 1, term_key, display_text))
            self.term_to_tree_item[term_key] = item_id
            self.term_to_original_index[term_key] = i

    def update_data_and_tree(self, term_key, new_text):
        lang_index = self._get_selected_language_index()
        original_index = self.term_to_original_index.get(term_key)
        if lang_index is None or original_index is None: return

        if self.file_mode == "standard":
            self.terms_list_ref[original_index]['Languages']['Array'][lang_index] = new_text
        else:
            self.terms_list_ref[original_index]['intro']['values']['Array'][lang_index] = new_text

        item_id = self.term_to_tree_item[term_key]
        current_values = list(self.tree.item(item_id, "values"))
        current_values[2] = new_text.replace('\n', ' ').strip()[:100]
        self.tree.item(item_id, values=tuple(current_values))

    def save_from_editor(self):
        if self.currently_editing_term_key:
            new_text = self.editor_text.get("1.0", "end-1c")
            self.update_data_and_tree(self.currently_editing_term_key, new_text)

    def _get_selected_language_index(self):
        try: return int(self.language_var.get().split(' ')[1])
        except: return None

    def on_language_change(self, event=None):
        self.populate_treeview()

    def on_drop(self, event):
        filepath = self.tk.splitlist(event.data)[0].strip('{}')
        self.load_file_logic(filepath)

    def open_file_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path: self.load_file_logic(path)

    def save_file(self):
        if self.current_filepath: self._write_to_file(self.current_filepath)
        else: self.save_file_as()

    def save_file_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path: 
            self.current_filepath = path
            self._write_to_file(path)

    def _write_to_file(self, filepath):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Success", "File saved.")
        except Exception as e: messagebox.showerror("Error", str(e))

    def find_next(self):
        query = self.search_entry.get().lower()
        if not query: return
        all_items = self.tree.get_children()
        curr = self.tree.focus()
        idx = (all_items.index(curr) + 1) if curr in all_items else 0
        for i in range(len(all_items)):
            item = all_items[(idx + i) % len(all_items)]
            if query in self.tree.item(item, "values")[2].lower():
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item)
                return

    def replace_selected(self):
        query = self.search_entry.get()
        rep = self.replace_entry.get()
        if not query or self.editor_text.cget("state") == "disabled": return
        txt = self.editor_text.get("1.0", "end-1c")
        new_txt, count = re.subn(re.escape(query), rep, txt, count=1, flags=re.IGNORECASE)
        if count > 0:
            self.editor_text.delete("1.0", "end")
            self.editor_text.insert("1.0", new_txt)

    def replace_all(self):
        query = self.search_entry.get()
        rep = self.replace_entry.get()
        if not query or not messagebox.askyesno("Confirm", "Replace all?"): return
        count = 0
        lang_idx = self._get_selected_language_index()
        for item_id in self.tree.get_children():
            key = self.tree.item(item_id, "values")[1]
            idx = self.term_to_original_index[key]
            if self.file_mode == "standard":
                old = self.terms_list_ref[idx]['Languages']['Array'][lang_idx]
            else:
                old = self.terms_list_ref[idx]['intro']['values']['Array'][lang_idx]
            
            new_text, n = re.subn(re.escape(query), rep, old, flags=re.IGNORECASE)
            if n > 0:
                self.update_data_and_tree(key, new_text)
                count += n
        messagebox.showinfo("Done", f"Replaced {count} items.")

    def export_to_txt(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if not path: return
        lang_idx = self._get_selected_language_index()
        with open(path, 'w', encoding='utf-8') as f:
            for item_id in self.tree.get_children():
                key = self.tree.item(item_id, "values")[1]
                idx = self.term_to_original_index[key]
                txt = self.terms_list_ref[idx]['Languages']['Array'][lang_idx] if self.file_mode=="standard" else self.terms_list_ref[idx]['intro']['values']['Array'][lang_idx]
                f.write(f'"{txt.replace(chr(34), chr(34)*2)}"\n')

    def import_from_txt(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if not path: return
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        items = self.tree.get_children()
        for item_id, line in zip(items, lines):
            line = line.strip()
            if line.startswith('"') and line.endswith('"'): line = line[1:-1].replace('""', '"')
            self.update_data_and_tree(self.tree.item(item_id, "values")[1], line)

if __name__ == "__main__":
    app = I2Editor()
    app.mainloop()
