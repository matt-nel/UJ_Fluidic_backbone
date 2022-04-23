"""
    Holds custom exceptions for the fluidic backbone code

"""


class FBError(Exception):
    """
    Base exception for Fluidic Backbone
    """


class FBConfigurationError(FBError):
    """
    JSON file not found, or invalid JSON file
    """


class FBModuleNotFoundError(FBError):
    """
    Module is not present
    """


class FBInvalidCommandError(FBError):
    """
    Command sent to manager is not present or is not recognised
    """