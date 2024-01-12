import time
import queue
import random
import script
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import asyncio
import telegram

stop_event = threading.Event()
print_queue = queue.Queue()

# Function to print to the text area
def output_to_textarea():
    while not print_queue.empty():
        text = print_queue.get()
        if "TMSG" in text:
            send_telegram_message(text.replace("TMSG ", ""))
            continue
        text_area.configure(state='normal')
        text_area.insert(tk.END, text + '\n')
        text_area.configure(state='disabled')
        text_area.see(tk.END)

    # Schedule this function to check for new messages every 100ms
    root.after(100, output_to_textarea)

def run_monitor_site():
    while not stop_event.is_set():
        try:
            print_queue.put("====================== Open New Browser ======================")
            print("====================== Open New Browser ======================")
            script.monitor_site(data, print_queue, stop_event, random.randint(200, 400))
        except Exception as e:
            print(f"Error: {e}")
            print_queue.put(f"Error: {str(e)}")

        # Wait for a random time or until the stop event is set
        t = random.randint(10, 45)
        for tt in range(t // 2):
            if stop_event.is_set():
                break
            print_queue.put(f'Waiting... {t - tt * 2}s')
            time.sleep(2)
        
        print_queue.put('====================================')
        
bot = telegram.Bot(token='6220637553:AAH55JhQnl9e-93191bfDEQJVGQn_KNpO2k')
def send_telegram_message(message):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.send_message(chat_id='-977055796', text=message))

# Function to update the data list and manage checkbuttons' state
def toggle_start_stop():
    global monitor_thread

    # Toggle the running state
    is_running = start_stop_var.get()
    
    # Update the checkbuttons' state
    p006_toggle.configure(state=tk.DISABLED if is_running else tk.NORMAL)
    p041_toggle.configure(state=tk.DISABLED if is_running else tk.NORMAL)
    p003_toggle.configure(state=tk.DISABLED if is_running else tk.NORMAL)

    # Update the status label color and font size
    status_label.configure(foreground="green" if is_running else "red", 
                           font=('Helvetica', 20, 'bold'))
    status_var.set("Running" if is_running else "Stopped")
    
    # Update the data list
    if is_running:
        data.clear()  # Clear the data list when starting
        if p006_var.get(): data.append('P006')
        if p003_var.get(): data.append('P003')
        if p041_var.get(): data.append('P041')

        # Output the current data list to the text area
        # print_queue.put("Data: " + str(data))
        print("Data: " + str(data))
        
        stop_event.clear()
        monitor_thread = threading.Thread(target=run_monitor_site, daemon=True)
        monitor_thread.start()
    else:
        stop_event.set()
        data.clear()  # Optionally clear the data list when stopping
        monitor_thread.join()
    

# Function to add or remove a value from the data list based on a checkbutton
def add_remove_data(item, var):
    if var.get():
        if item not in data:
            data.append(item)
    else:
        if item in data:
            data.remove(item)

# Initialize the main window
root = tk.Tk()
root.title("Theopenstage Bot")

# Create an empty data list
data = []

# Set the style of the widgets
style = ttk.Style()
style.theme_use('default')  # You can change the theme to 'clam', 'alt', 'default', 'classic', or 'vista'

# Configure the style of the label and checkbutton
style.configure('TLabel', font=('Helvetica', 20, 'bold'))
style.configure('TCheckbutton', font=('Helvetica', 20, 'bold'), indicatoron=False, padding=20)

# Define variables for the toggle switches
start_stop_var = tk.BooleanVar(value=False)  # Initially off
p006_var = tk.BooleanVar(value=False)
p041_var = tk.BooleanVar(value=False)
p003_var = tk.BooleanVar(value=False)
status_var = tk.StringVar(value="Stopped")

# Frame for the checkbuttons
frame = ttk.Frame(root, padding="10")
frame.pack(fill='x')

# Add the start/stop toggle
start_stop_toggle = ttk.Checkbutton(frame, text='START/STOP', variable=start_stop_var, command=toggle_start_stop)
start_stop_toggle.pack(fill='x', expand=True)

# Add the P006 monitor toggle
p006_toggle = ttk.Checkbutton(frame, text='P006 monitor', variable=p006_var, command=lambda: add_remove_data('P006', p006_var))
p006_toggle.pack(fill='x', expand=True)

# Add the P041 monitor toggle
p041_toggle = ttk.Checkbutton(frame, text='P041 monitor', variable=p041_var, command=lambda: add_remove_data('P041', p041_var))
p041_toggle.pack(fill='x', expand=True)

# Add the P003 monitor toggle
p003_toggle = ttk.Checkbutton(frame, text='P003 monitor', variable=p003_var, command=lambda: add_remove_data('P003', p003_var))
p003_toggle.pack(fill='x', expand=True)

# Frame for the status label
status_frame = ttk.Frame(root, padding="10")
status_frame.pack(fill='x')

# Add a status label to the status frame
status_label = ttk.Label(status_frame, textvariable=status_var, font=('Helvetica', 20, 'bold'), foreground="red")
status_label.pack()

# Text area for displaying outputs
text_area = scrolledtext.ScrolledText(root, state='disabled', height=10)
text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Start the update_text_area periodic call
root.after(100, output_to_textarea)

# Start the main loop
root.mainloop()
