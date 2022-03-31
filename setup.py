from setuptools import setup, find_packages

setup(
    name="UJ_FB",
    version="1.0",
    description="Package to control open-source hardware via Arduino microcontrollers for chemical synthesis",
    author="Matthew Nel",
    author_email="mattnel@outlook.com",
    url="https://github.com/Pajables/UJ_Fluidic_backbone.git",
    package_dir={"": "src"},
    packages=find_packages("src"),
    package_data={"UJ_FB": ["configs/*.json", "*.ico", "*.png"]},
    install_requires=["pyserial", "networkx", "pillow", "numpy", "opencv-python", "requests"]
)