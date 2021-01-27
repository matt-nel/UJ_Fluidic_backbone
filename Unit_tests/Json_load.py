import os
import json


script_dir = os.path.dirname(__file__)  # get absolute directory of script
cm_config = os.path.join(script_dir, "data.json")
with open(cm_config) as file:
    data = json.load(file)
print("waiting")