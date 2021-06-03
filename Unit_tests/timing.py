from timeit import timeit


class DataClass:
    def __init__(self):
        self.outer = {'inner': 'aspirate'}
        self.inner = 'aspirate'


print('long string', timeit("long_string == 'aspirate'", "long_string = 'aspirate'"))

print('short string', timeit("short_string == 'asp'", "short_string = 'asp'"))

print('dict with long string', timeit("comp['outer'] == 'aspirate'", "comp = {'outer': 'aspirate'}"))

print('nested dict', timeit("comp['outer']['inner'] == 'aspirate'", "comp = {'outer' : {'inner': 'aspirate'}}"))

print('data structure', timeit("dc.outer['inner'] == 'aspirate'", "dc = DataClass()", globals=globals()))

print('data structure simple', timeit("dc.inner == 'aspirate'", "dc = DataClass()", globals=globals()))

print('searching big dict', timeit("my_dict.get('crayon')", "my_dict = {'crayon': 1, 'duck': 2, 'tree':3, 'usb':4, 'mouse':5, 'rabbit':6, 'glue':7, 'note':8, 'model':9, 'train':10, 'fillibuister':11, 'coding':12, 'key':'yes!'}"))

