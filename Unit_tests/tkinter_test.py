import os
import tkinter
from PIL import ImageTk, Image

root=tkinter.Tk()

script_dir = os.path.dirname(__file__)
image_dir = os.path.join(script_dir, 'valve.png')
valve_image = ImageTk.PhotoImage(Image.open(image_dir))
img_label = tkinter.Label(root, image=valve_image)
img_label.grid(row=1, column=1)

root.mainloop()