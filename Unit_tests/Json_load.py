

class dummy:
    def __init__(self, name, location, sex, age):
        self.name = name
        self.location = location
        self.sex = sex
        self.age = age


person = {'name': 'Fillibuster McPants', 'location': 'Mars', 'sex': "yeah baby", 'age': 69}

my_class = dummy(**person)
print(my_class.name, my_class.age, my_class.location, my_class.sex)