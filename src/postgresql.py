import os
from os.path import splitext

import psycopg2
from psycopg2.extras import DictCursor
from tqdm import tqdm

from utils import extract_video_code, extract_video_resolution_ffmpeg, extract_video_resolution_opencv, has_subtitles_uncensored, is_video_split

SERVER_PATH = "/videos"
DATABASE = "JAV"
HOST = "192.168.1.111"
USER = "postgres"
PASSWORD = "Boxerlee2015!13"
PORT = "5432"


class PostgresSQL:
    def __init__(self):
        self.postgres_connection = self.connect_db()

    def connect_db(self, database=DATABASE, host=HOST, user=USER, password=PASSWORD, port=PORT, cursor_factory=DictCursor):
        try:
            return psycopg2.connect(database=database, host=host, user=user, password=password, port=port, cursor_factory=cursor_factory)
        except (Exception, psycopg2.DatabaseError):
            print("Server Connection Failed")

            return None

    # Database I/O Functions
    def find(self, video_code: str):
        sql = """SELECT * FROM videos WHERE video_code = %s"""
        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, (video_code,))

            return cursor.fetchall()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def find_all(self, actress: str):
        sql = """SELECT * FROM videos WHERE actress = %s ORDER BY video_code ASC"""
        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, (actress,))

            return cursor.fetchall()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def find_all_actresses(self):
        sql = """SELECT DISTINCT actress FROM videos ORDER BY actress ASC"""
        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql)

            return cursor.fetchall()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def delete(self, video_code: str):
        sql = """DELETE FROM videos WHERE video_code = %s"""
        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, (video_code,))
            self.postgres_connection.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def update(self, video_info: dict):
        sql = "UPDATE videos SET "
        for key, property in video_info.items():
            if key == "video_code":
                continue

            sql += f"{key} = %({key})s, "

        sql = sql[:-2]
        sql += " WHERE video_code = %(video_code)s"

        try:
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, video_info)
            self.postgres_connection.commit()

            print(f"Updated {video_info['video_code']}")
        except (Exception, psycopg2.DatabaseError) as error:
            print("Error updating data: %s" % error)

    def upsert(self, video_info: dict):
        """
        Upsert the video information into the videos table.

        Args:
            video_info (dict): A dictionary containing the video information.
        """
        sql = """INSERT INTO videos (actress, video_code, subtitles, uncensored, width, height, opened, video_split, subtitle_created, deleted, split_names) VALUES (%(actress)s, %(video_code)s, %(subtitles)s, %(uncensored)s, %(width)s, %(height)s, %(opened)s, %(video_split)s, %(subtitle_created)s, %(deleted)s , %(split_names)s) ON CONFLICT (video_code) DO UPDATE SET subtitles = %(subtitles)s, uncensored = %(uncensored)s, width = %(width)s, height = %(height)s, opened = %(opened)s, video_split = %(video_split)s, subtitle_created = %(subtitle_created)s, deleted = %(deleted)s , split_names = %(split_names)s"""

        try:
            # execute the SQL query
            cursor = self.postgres_connection.cursor()
            cursor.execute(sql, video_info)
            # commit the changes to the database
            self.postgres_connection.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            # if an error occurs, rollback the changes
            print("Error inserting/updating data: %s" % error)
            self.postgres_connection.rollback()

    # Database Sync Functions
    def update_video_resolutions(self, actress: str):
        """
        Updates the video resolutions in the PostgreSQL database.

        Args:
            actress (str): The name of the actress.
        """
        for video in os.listdir(os.path.join(SERVER_PATH, actress)):
            if video.endswith(".mp4"):
                video_code = extract_video_code(video)

                try:
                    width, height = extract_video_resolution_ffmpeg(os.path.join(SERVER_PATH, actress, video))
                except Exception:
                    continue

                print(f"{video_code}: {width} x {height}")

                # Update the video information in the PostgreSQL database
                self.update(
                    {
                        "video_code": video_code,
                        "width": width,
                        "height": height,
                    }
                )

    def sync_files_with_database(self, actress: str):
        """
        Sync database with actress's videos.
        """

        video_code_set = set()

        actress_videos = list(filter(lambda video: video.endswith(".mp4"), os.listdir(os.path.join(SERVER_PATH, actress))))
        actress_subtitles = list(filter(lambda video: video.endswith(".srt"), os.listdir(os.path.join(SERVER_PATH, actress))))
        for video in tqdm(actress_videos, desc=f"{actress}", position=1, colour="red", leave=False):
            video_code = extract_video_code(video)

            if video_code in video_code_set:
                continue

            video_code_set.add(video_code)

            subtitles, uncensored = has_subtitles_uncensored(video)

            try:
                width, height = extract_video_resolution_ffmpeg(os.path.join(SERVER_PATH, actress, video))
            except Exception:
                try:
                    width, height = extract_video_resolution_opencv(os.path.join(SERVER_PATH, actress, video))
                except Exception:
                    print(f"Failed to get resolution for {video}")
                    width, height = None, None
                    continue

            split_names = [splitext(actress_video)[0] for actress_video in actress_videos if video_code in actress_video]

            video_info = {
                "actress": actress,
                "video_code": video_code,
                "subtitles": subtitles,
                "uncensored": uncensored,
                "width": width,
                "height": height,
                "opened": True,
                "video_split": is_video_split(video),
                "subtitle_created": True if splitext(video)[0] + ".srt" in actress_subtitles else False,
                "deleted": False,
                "split_names": split_names,
            }

            try:
                self.upsert(video_info)

            except Exception:
                print(f"Failed to Upsert: {video_code}")
                continue

    def sync_database_with_files(self, actress: str):
        videos_in_db = self.find_all(actress)

        # If the actress directory does not exist, upsert all the videos as deleted
        if not os.path.exists(os.path.join(SERVER_PATH, actress)):
            for video in videos_in_db:
                video_info = {
                    "actress": actress,
                    "video_code": video["video_code"],
                    "subtitles": video["subtitles"],
                    "uncensored": video["uncensored"],
                    "width": video["width"],
                    "height": video["height"],
                    "opened": video["opened"],
                    "video_split": video["video_split"],
                    "subtitle_created": video["subtitle_created"],
                    "deleted": True,
                    "split_names": None,
                }

                try:
                    self.upsert(video_info)
                    # print(f"Upserted: {video_code}")
                except Exception:
                    print(f"Failed to Upsert: {video['video_code']}")
                    continue

        videos_in_server = list(filter(lambda video: video.endswith(".mp4"), os.listdir(os.path.join(SERVER_PATH, actress))))
        for video in tqdm(videos_in_db, desc=f"Syncing {actress}", position=1, colour="red", leave=False):
            if video["video_code"] not in list(set(map(lambda video: extract_video_code(video), videos_in_server))):
                video_info = {
                    "actress": actress,
                    "video_code": video["video_code"],
                    "subtitles": video["subtitles"],
                    "uncensored": video["uncensored"],
                    "width": video["width"],
                    "height": video["height"],
                    "opened": video["opened"],
                    "video_split": video["video_split"],
                    "subtitle_created": video["subtitle_created"],
                    "deleted": True,
                    "split_names": None,
                }

                try:
                    self.upsert(video_info)
                    # print(f"Upserted: {video_code}")
                except Exception:
                    print(f"Failed to Upsert: {video['video_code']}")
                    continue
