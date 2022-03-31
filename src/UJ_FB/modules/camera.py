from UJ_FB.modules import modules
import logging
import cv2 as cv
from threading import Thread, Lock


class Camera(modules.Module):
    """Class for managing the robot's camera
        Inherits from general module class
    """
    def __init__(self, name, module_info, manager):
        super(Camera, self).__init__(name, module_info, None, manager)
        module_config = module_info["mod_config"]
        self.roi = module_config["ROI"]
        self.cap = cv.VideoCapture(0)
        self.last_frame = None
        self.frame_lock = Lock()
        self.capture_thread = Thread(target=self.read_frames)
        self.exit_flag = False
        self.capture_thread.start()

    def read_frames(self):
        while not self.exit_flag:
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.last_frame = frame
        self.cap.release()

    def capture_image(self, task):
        with self.frame_lock:
            if self.last_frame is None:
                self.write_log("Unable to receive frame from video stream", level=logging.ERROR)
                task.error = True
            else:
                frame = self.last_frame
                return frame

    def send_image(self, listener, metadata, task):
        num_retries = 0
        while num_retries < 5:
            frame = self.capture_image(task)
            if task.error:
                return
            ret, enc_image = cv.imencode(".png", frame)
            response = listener.send_image(metadata, enc_image)
            if response is not False:
                if response.ok:
                    break
                else:
                    num_retries += 1
            else:
                num_retries += 1
            self.write_log(f"Received response: {response.json()}")
        if num_retries > 4:
            task.error = True
            self.write_log("Unable to send image", level=logging.WARNING)

    def resume(self, command_dicts):
        return True
