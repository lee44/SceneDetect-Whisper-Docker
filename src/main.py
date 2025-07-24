import logging
import multiprocessing
import os
import queue
import shutil
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from posixpath import splitext
from queue import Queue

import schedule

from scene_detect import SceneDetect

VIDEO_CONTAINER_PATH = "/videos"

logger = logging.getLogger("scene_detect_logger")
logger.propagate = False
logger.setLevel(logging.INFO)

if not os.path.exists(os.path.join(VIDEO_CONTAINER_PATH, "logs")):
    os.makedirs(os.path.join(VIDEO_CONTAINER_PATH, "logs"), exist_ok=True)

# Set up a rotating file handler
file_handler = RotatingFileHandler(
    os.path.join(VIDEO_CONTAINER_PATH, "logs", "app.log"),  # Log file name
    maxBytes=1000000,  # Maximum size of a log file in bytes before rotation
    backupCount=3,  # Number of backup files to keep
    mode="a+",  # Append mode
)

console_handler = logging.StreamHandler()

formatter = logging.Formatter("\n[%(asctime)s] %(message)s", "%Y-%m-%d | %H:%M:%S")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

jobqueue: Queue = queue.Queue(1)


def worker_main():
    while 1:
        job_func = jobqueue.get()
        job_func()
        jobqueue.task_done()


def load_folders():
    folders = []
    i = 1
    while True:
        folder = os.environ.get(f"FOLDER_{i}")
        if folder:
            folders.append(folder)
            i += 1
        else:
            break

    return folders


def main():
    folders = load_folders()

    for folder in folders:
        video_path = os.path.join(VIDEO_CONTAINER_PATH, folder)
        scene_detect = SceneDetect(folder, video_path)

        if os.path.exists(video_path):
            scene_path = os.path.join(VIDEO_CONTAINER_PATH, folder, "scenes")
            if not os.path.exists(scene_path):
                logger.info(f"Scene Directory {scene_path} created.")
                os.makedirs(scene_path, exist_ok=True)

            for video in os.listdir(video_path):
                if video.endswith(".mp4"):
                    scene_detect.extract_scenes(video)

            for scene in os.listdir(scene_path):
                if not os.path.exists(os.path.join(VIDEO_CONTAINER_PATH, folder, splitext(scene)[0] + ".mp4")):
                    continue

                try:
                    scene_detect.split_scenes(
                        scene_path=os.path.join(VIDEO_CONTAINER_PATH, folder, "scenes", scene),
                        video_path=os.path.join(VIDEO_CONTAINER_PATH, folder, splitext(scene)[0] + ".mp4"),
                    )

                    scenes = scene_detect.serialize_scenes(scene_path=os.path.join(VIDEO_CONTAINER_PATH, folder, "scenes", scene))
                    videos = list(filter(lambda x: x.endswith(".mp4") and splitext(scene)[0] in x, os.listdir(video_path)))

                    logger.info(f"Scenes({len(scenes)}): {scenes}")
                    logger.info(f"Videos({len(videos) - 1}): {videos}")

                    video_path = os.path.join(VIDEO_CONTAINER_PATH, folder, splitext(scene)[0] + ".mp4")
                    if len(scenes) == len(videos) - 1:
                        logger.info(f"Moving {video_path} to trash.")

                        recycle_bin_path = os.path.join(VIDEO_CONTAINER_PATH, ".Recycle.Bin", folder)
                        if not os.path.exists(recycle_bin_path):
                            os.makedirs(recycle_bin_path, exist_ok=True)

                        shutil.move(video_path, recycle_bin_path)

                except Exception as e:
                    logger.error(f"Error: {e}")

        # else:
        #     logger.info(f"Video path: {video_path} does not exist.")


jobqueue.put(main)

schedule.every(30).minutes.do(jobqueue.put, main)

worker_thread = threading.Thread(target=worker_main)
worker_thread.start()

while True:
    schedule.run_pending()
    time.sleep(1)
