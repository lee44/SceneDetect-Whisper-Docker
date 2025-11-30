import os
import re
import time
from datetime import datetime

import cv2
import ffmpeg


def get_modified_time(video_path: str):
    """
    Get the modified time of the video file.

    Args:
        video_path (str): The path to the video file.

    Returns:
        str: The modified time of the video file.
    """
    # Get the timestamp
    ti_m = os.path.getmtime(video_path)

    m_ti = time.ctime(ti_m)

    # Using the timestamp string to create a time object/structure
    # t_obj = time.strptime(m_ti)

    # Transforming the time object to a timestamp of ISO 8601 format
    # T_stamp = time.strftime("%Y-%m-%d %H:%M:%S", t_obj)

    datetime_object = datetime.strptime(m_ti, "%a %b %d %H:%M:%S %Y")

    return datetime_object


def extract_video_resolution_ffmpeg(video_path: str) -> tuple:
    """
    Extracts the video resolution from the video file.

    Args:
        video_path (str): The path to the video file.

    Returns:
        tuple: A tuple containing the width and height of the video resolution.
    """
    video_streams = ffmpeg.probe(video_path, select_streams="v")

    return video_streams["streams"][0]["width"], video_streams["streams"][0]["height"]


def extract_video_resolution_opencv(video_path):
    """
    Retrieves the width and height (resolution) of a video file using OpenCV.
    """
    # Check if the file exists
    if not os.path.exists(video_path):
        return f"Error: Video file not found at '{video_path}'"

    # Create a VideoCapture object
    cap = cv2.VideoCapture(video_path)

    # Check if the video file was opened successfully
    if not cap.isOpened():
        return f"Error: Could not open video file at '{video_path}'"

    # Get the width and height properties
    # cv2.CAP_PROP_FRAME_WIDTH is the index for width (often 3)
    # cv2.CAP_PROP_FRAME_HEIGHT is the index for height (often 4)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Release the video capture object
    cap.release()

    return frame_width, frame_height


def extract_video_code(video: str):
    """
    Extract the video code, excluding -RM, -SUB, and trailing -001, -002, etc from the video filename.

    Args:
        video (str): The name of the video file.

    Returns:
        str: The extracted video code.
    """
    # Remove the '.mp4' extension from the video name
    video = video.replace(".mp4", "")

    # Split the video name into parts using '-' as the delimiter
    video_name_split = video.split("-")

    # Check the length of the video name split
    if len(video_name_split) == 4:
        # If the length is 4, remove the last part of the video name
        video = video[: video.rfind("-")]
    elif len(video_name_split) == 3:
        # If the length is 3, check if the video name contains '-SUB' or '-RM'
        if "-SUB" not in video and "-RM" not in video:
            # If it does not contain '-SUB' or '-RM', remove the last part of the video name
            video = video[: video.rfind("-")]

    # Return the extracted video code after removing leading and trailing whitespace
    return video.replace("-RM", "").replace("-SUB", "").strip()


def is_video_split(video: str) -> bool:
    """
    Check if the video is a split video based on its name.

    Args:
        video (str): The name of the video file.

    Returns:
        bool: True if the video is a split video, False otherwise.
    """
    # Regular expression pattern to match the end of the video name if it is a split video
    pattern = r"RM-\d{3}|SUB-\d{3}"

    # Return True if the video name matches the pattern, False otherwise
    return bool(re.search(pattern, video))


def has_subtitles_uncensored(video: str):
    """
    Check if the video has subtitles or uncensored.

    Args:
        video (str): The name of the video file.

    Returns:
        tuple: A tuple containing the subtitles status (bool) and uncensored status (bool).
    """
    # Initialize the subtitles and uncensored status as False
    subtitles = False
    uncensored = False

    # Check if the video contains '-SUB'
    if "-SUB" in video:
        # If it does, set the subtitles status to True
        subtitles = True
    # Check if the video contains '-RM'
    elif "-RM" in video:
        # If it does, set the uncensored status to True
        uncensored = True

    # Return the subtitles and uncensored status as a tuple
    return subtitles, uncensored
