import threading


class MyThread(threading.Thread):
    def __init__(self, name, lock):
        threading.Thread.__init__(self)
        self.name = name
        self.query = ''
        self.lock = lock

    def run(self):
        self.the_illusion_of_work()
        while self.query != 'n':
            with self.lock:
                self.query = input(f"Thead {self.name} Would you like to do that again?")
                if self.query != 'n':
                    self.the_illusion_of_work()
        print(f"Goodbye from Thread {self.name}")

    def the_illusion_of_work(self):
        for i in range(0, 10):
            print(f"Thread {self.name}'s number is {i}")


lock = threading.Lock()
for test in range(1, 5):
    test = MyThread(test, lock).start()
