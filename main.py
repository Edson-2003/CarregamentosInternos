import tkinter as tk
from tkinter import ttk
from gui import Aplicacao

def main():
    root = tk.Tk()
    
    style = ttk.Style()
    if 'clam' in style.theme_names():
        style.theme_use('clam')
        
    app = Aplicacao(root)
    root.mainloop()

if __name__ == "__main__":
    main()
