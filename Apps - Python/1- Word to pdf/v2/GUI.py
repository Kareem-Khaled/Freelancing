import threading
import tkinter as tk
from main import run
from tkinter import ttk
from tkinter import filedialog

font = ('Helvetica', 18)
font2 = ('Helvetica', 12)

def running():
    button_start["text"] = "Running..."
    button_start["state"] = tk.DISABLED
    button_browse_files["state"] = tk.DISABLED
    button_browse_word["state"] = tk.DISABLED
    entry_key_column["state"] = tk.DISABLED
    entry_value_column["state"] = tk.DISABLED
    button_output["state"] = tk.DISABLED

def reset():
    button_start["state"] = tk.NORMAL
    button_start["text"] = "Start"
    progress_var["value"] = 0
    button_browse_files["state"] = tk.NORMAL
    button_browse_word["state"] = tk.NORMAL
    entry_key_column["state"] = tk.NORMAL
    entry_value_column["state"] = tk.NORMAL
    button_output["state"] = tk.NORMAL

def browse_folder(entry_var):
    folder_path = filedialog.askdirectory()
    entry_var.set(folder_path)

def browse_files(entry_var, filetypes):
    file_paths = filedialog.askopenfilenames(filetypes=filetypes)
    entry_var.set("; ".join(file_paths))

def start_processing(entry_word_file, entry_files, key_column_var, value_column_var, progress_var):
    word_file_path = entry_word_file.get().split("; ")[-1]
    file_paths = entry_files.get().split("; ")
    key_column = key_column_var.get()
    value_column = value_column_var.get()
    output_folder = output_folder_var.get()

    if not word_file_path or not file_paths or not key_column or not value_column or not output_folder:
        tk.messagebox.showwarning("Warning", "Please fill in all required fields.")
        return

    running()

    # Print the paths
    print("Output Folder:" + output_folder)
    print("Word File Path:", word_file_path)
    print("Excel Files Paths:", file_paths)

    # Start the processing
    processing_thread = threading.Thread(target=run, args=(file_paths, word_file_path, key_column, value_column, progress_var, output_folder))
    processing_thread.start()

    # Check if the thread is still running
    root.after(1000, check_thread, processing_thread, button_start, progress_var)

def check_thread(thread, button_start, progress_var):
    if thread.is_alive():
        root.after(1000, check_thread, thread, button_start, progress_var)
    else:
        reset()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x400")
    root.resizable(False, False)
    root.title("Fill Word Data App")

    word_file_var = tk.StringVar()
    excel_files_var = tk.StringVar()
    key_column_var = tk.StringVar()
    value_column_var = tk.StringVar()
    output_folder_var = tk.StringVar()

    # Section 0
    tk.Label(root, text="Fill Word Data App", font=("Helvetica", 20, "bold")).grid(row=0, column=1, pady=20)

    # Section 1
    tk.Label(root, text="Select Word File:", font=font).grid(row=1, column=0, pady=5, padx=10, sticky="w")
    entry_word_file = tk.Entry(root, state="readonly", textvariable=word_file_var, font=font2)
    entry_word_file.grid(row=1, column=1, pady=5, padx=10, sticky="w")
    
    button_browse_word = tk.Button(root, text="Browse Word File", 
                                   command=lambda: browse_files(word_file_var, [("Word Files", "*.doc;*.docx")]),
                                   font=font2, bg="lightblue", width=15, padx=10)
    button_browse_word.grid(row=1, column=2, pady=5, padx=10, sticky="w")

    # Section 2
    tk.Label(root, text="Select Excel Files:", font=font).grid(row=2, column=0, pady=5, padx=10, sticky="w")
    entry_files = tk.Entry(root, state="readonly", textvariable=excel_files_var, font=font2)
    entry_files.grid(row=2, column=1, pady=5, padx=10, sticky="w")

    button_browse_files = tk.Button(root, text="Browse Excel Files", 
                                    command=lambda: browse_files(excel_files_var, [("Excel Files", "*.xlsx;*.xls")]),
                                    font=font2, bg="lightblue", width=15, padx=10)
    button_browse_files.grid(row=2, column=2, pady=5, padx=10, sticky="w")

    # Section 3
    tk.Label(root, text="Key Column:", font=font).grid(row=3, column=0, pady=5, padx=10, sticky="w")
    entry_key_column = tk.Entry(root, textvariable=key_column_var, font=font2)
    entry_key_column.grid(row=3, column=1, pady=5, padx=10, sticky="w")

    button_output = tk.Button(root, text="Browse Output Folder", 
                             command=lambda: browse_folder(output_folder_var),
                             font=font2, bg="lightblue", width=15, padx=10)
    button_output.grid(row=3, column=2, pady=5, padx=10, sticky="w")

    # Section 4
    tk.Label(root, text="Value Column:", font=font).grid(row=4, column=0, pady=5, padx=10, sticky="w")
    entry_value_column = tk.Entry(root, textvariable=value_column_var, font=font2)
    entry_value_column.grid(row=4, column=1, pady=5, padx=10, sticky="w")

    # Start Button    
    button_start = tk.Button(root, text="Start", 
                             command=lambda: start_processing(entry_word_file, entry_files, entry_key_column, entry_value_column, progress_var),
                             font=font2, bg="lightblue", width=15, padx=10)
    button_start.grid(row=4, column=2, pady=5, padx=10, sticky="w")

    progress_var = ttk.Progressbar(root, orient="horizontal", length=600, mode="determinate")
    progress_var.grid(row=5, column=0, columnspan=5, pady=50, padx=100)

    root.mainloop()