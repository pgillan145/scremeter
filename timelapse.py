#!/usr/bin/env python3

import cv2
from datetime import datetime,timedelta
import os
import re
import scremeter
import sys
import time

scremeter.turnWriteCacheOff()

def main():
    codec = cv2.VideoWriter_fourcc(*'MJPG')
    ext = 'avi'

    width = 1920
    height = 1080
    fps = 30

    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_FOURCC, codec)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    #output = cv2.VideoWriter(f'./cam_video.{ext}', codec, float(fps), (width, height))
    
    base_path = f"/home/pgillan/Documents/scremus/images/{scremeter.title()}"

    last = datetime.now()
    while (True):
        try:
            # just run once a second
            time.sleep(.5)

            if (last + timedelta(seconds=1) < datetime.now()):
                last = datetime.now()
                ret, frame = cap.read()
                hms = last.strftime('%Y-%m-%d-%H_%M_%S')
                print('{}-{}.{}'.format(base_path, hms, 'jpg'))
                cv2.imwrite('{}-{}.{}'.format(base_path, hms, 'jpg'), frame)

        except KeyboardInterrupt:
            break

    cap.release()
    #output.release()
    cv2.destroyAllWindows()

    print("")


main()
