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
from subtitle import SubtitleGenerator

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


def load_actors():
    actors = []
    i = 1
    while True:
        actor = os.environ.get(f"ACTOR_{i}")
        if actor:
            actors.append(actor)
            i += 1
        else:
            break

    return actors


def main():
    actors = load_actors()

    for actor in actors:
        actor_path = os.path.join(VIDEO_CONTAINER_PATH, actor)
        scene_detect = SceneDetect(actor, actor_path)
        subtitle = SubtitleGenerator(actor, actor_path)

        lock = multiprocessing.Manager().Lock()

        if os.path.exists(actor_path):
            scene_path = os.path.join(VIDEO_CONTAINER_PATH, actor, "scenes")
            if not os.path.exists(scene_path):
                logger.info(f"Scene Directory {scene_path} created.")
                os.makedirs(scene_path, exist_ok=True)

            for video in os.listdir(actor_path):
                if video.endswith(".mp4"):
                    scene_detect.extract_scenes(video)

            for scene in os.listdir(scene_path):
                if scene.endswith(".json"):
                    try:
                        scene_detect.split_scenes(
                            os.path.join(VIDEO_CONTAINER_PATH, actor, "scenes", scene),
                            os.path.join(VIDEO_CONTAINER_PATH, actor, splitext(scene)[0] + ".mp4"),
                        )

                        os.remove(os.path.join(VIDEO_CONTAINER_PATH, actor, splitext(scene)[0] + ".mp4"))

                    except Exception as e:
                        logger.error(f"Error splitting video: {e}")

            subtitle.mp_extract_audio(1, lock)
            subtitle.mp_generate_subtitle(1)

        else:
            logger.info(f"Actor path {actor_path} does not exist.")


jobqueue.put(main)

schedule.every(30).minutes.do(jobqueue.put, main)

worker_thread = threading.Thread(target=worker_main)
worker_thread.start()

while True:
    schedule.run_pending()
    time.sleep(1)
