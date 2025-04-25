import logging
import multiprocessing
import os
import queue
import threading
import time
from pathlib import Path
from posixpath import splitext
from queue import Queue

import schedule

from scene_detect import SceneDetect

logger = logging.getLogger("scene_detect_logger")
logger.propagate = False
logger.setLevel(logging.INFO)
formatter = logging.Formatter("\n[%(asctime)s] %(message)s", "%Y-%m-%d | %H:%M:%S")

handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

VIDEO_CONTAINER_PATH = "/videos"

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
                if scene.endswith(".json"):
                    try:
                        scene_detect.split_scenes(
                            os.path.join(VIDEO_CONTAINER_PATH, folder, "scenes", scene),
                            os.path.join(VIDEO_CONTAINER_PATH, folder, splitext(scene)[0] + ".mp4"),
                        )

                        if os.path.getsize(os.path.join(VIDEO_CONTAINER_PATH, folder, splitext(scene)[0] + ".mp4")) >= 25000:
                            os.remove(os.path.join(VIDEO_CONTAINER_PATH, folder, splitext(scene)[0] + ".mp4"))

                    except Exception as e:
                        logger.error(f"Error splitting video: {e}")

        else:
            logger.info(f"Video path: {video_path} does not exist.")


jobqueue.put(main)

schedule.every(30).minutes.do(jobqueue.put, main)

worker_thread = threading.Thread(target=worker_main)
worker_thread.start()

while True:
    schedule.run_pending()
    time.sleep(1)
