#todo add camera module class
from UJ_FB.Modules import modules
import logging
import cv2 as cv
import numpy as np


class Camera(modules.Module):
    """Class for managing the robot's camera
        Inherits from general module class
    """
    def __init__(self, name, module_info, manager):
        super(Camera, self).__init__(name, module_info, None, manager)
        module_config = module_info['mod_config']
        self.roi = module_config['ROI']
        self.cap = cv.VideoCapture(0)
        self.last_image = np.array([]) 

    def capture_image(self):
        ret, frame = self.cap.read()
        if not ret:
            self.write_log("Unable to receive frame from video stream", level=logging.ERROR)
        self.last_image = frame

    def encode_image(self):
        ret, enc_image = cv.imencode('.png', self.last_image)
        return enc_image