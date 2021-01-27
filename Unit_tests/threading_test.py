import threading

def action(i):
    print(i**2)


threading.Thread(target=action(2)).start()