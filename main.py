import json

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    file_name = 'B:/Root/Learning/UJ/Postgrad/Chemputer/Fluidic backbone/commanduino/examples/commanddevices/commandaccelstepper/demo.json'
    with open(file_name) as f:
        try:
            config_dict = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            # Printing "e" as well as it holds info on the line/column where the error occurred
            print(f"The JSON file provided {file_name} is invalid!/n{e}")
    print(config_dict)
    print(config_dict.items())
    print(list(config_dict.items()))
# See PyCharm help at https://www.jetbrains.com/help/pycharm/
