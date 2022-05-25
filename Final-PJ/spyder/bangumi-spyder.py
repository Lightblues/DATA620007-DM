""" 220525 @Lightblues
基于API的 bangumi.tv 爬虫, 将数据库换成了 mongo
API: https://bangumi.github.io/api/
"""

from requests_html import HTMLSession
import math, random
import os, sys, time
import lxml.html
import re
import collections
import mysql.connector
from bs4 import BeautifulSoup
import pandas as pd
import logging
import json
from datetime import datetime

import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection

from easonsi import utils
from config.config import header_bangumi

base_url = "https://api.bgm.tv"
url_s = "https://api.bgm.tv/v0/subjects/{}" # 329906
url_s_persons = "https://api.bgm.tv/v0/subjects/{}/persons"
url_s_characters = "https://api.bgm.tv/v0/subjects/{}/characters"
url_s_subjects = "https://api.bgm.tv/v0/subjects/{}/subjects"

class SpyderBangumi(object):
    def __init__(self) -> None:
        self.init_session(header_bangumi)
        self.db = MongoClient('mongodb://localhost:27017/').bangumi
        # self.init_logging()

    def init_session(self, header):
        session = HTMLSession()
        session.headers.update(header)
        self.session: HTMLSession = session
        
    def init_logging(self, logname=f"{__file__}", dir="logs/", level=logging.INFO):
        # 统一将日志记录在 logs 中, logname/taskname 不需要加后缀 .log
        os.makedirs(dir, exist_ok=True)
        logging.root.handlers = []
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
            level=level,
            handlers=[
                logging.FileHandler(os.path.join(dir, f"{logname}.log")),
                logging.StreamHandler()
            ]
        )
        
    def db_find_one(self, dbname, version="1", **query):
        collection = self.db[dbname]
        query["version"] = version
        r = collection.find_one(query)
        if r:
            return 0, r
        return -1, None

    def get_subject(self, subject_id, version="1"):
        collection: Collection = self.db.subject
        d = collection.find_one({
            "subject_id": subject_id,
            "version": version,
            "titlecn": {"$exists": True}
        })
        if d:
            return 0, d
        try:
            info = self.session.get(url_s.format(subject_id)).json()
            persons = self.session.get(url_s_persons.format(subject_id)).json()
            characters = self.session.get(url_s_characters.format(subject_id)).json()
            subjects = self.session.get(url_s_subjects.format(subject_id)).json()
            assert info and info["name"], f"{subject_id} - {info}"
            # assert persons, f"{subject_id} - {persons}"
            # assert characters, f"{subject_id} - {characters}"
            d = {
                "subject_id": subject_id,
                "title": info["name"],
                "titlecn": info["name_cn"],
                "info": info,
                "persons": persons,
                "characters": characters,
                "subjects": subjects,
                "version": version,
                "t_update": datetime.now()
            }
            collection.insert_one(d)
            return 1, d
        except Exception as e:
            # print(e)
            return -1, e
        
    def get_calendar(self, fn=None):
        """ 获取本季度番剧列表 """
        if fn is None:
            fn =  f"../data/calendar-{datetime.now().strftime('%Y%m%d')}.json"
        if os.path.exists(fn):
            return utils.LoadJson(fn)
        url = base_url + "/calendar"
        r = self.session.get(url)
        if r.status_code != 200:
            logging.error(f"{r.status_code} - {r.url}\n{r.text}")
        d = json.loads(r.text)
        utils.SaveJson(d, fn)
        return d
    
    def get_subjects_calendar(self, taskname="get_subjects_calendar"):
        """ 爬取列表对应的番剧信息 """
        self.init_logging(taskname)
        data = self.get_calendar()
        subject_ids = []
        for d in data:
            for item in d["items"]:
                subject_id = item["id"]
                subject_ids.append(subject_id)
        
        logging.info(f"start {taskname}.. total subjects: {len(subject_ids)}")
        count_success = count_crawled = 0
        for subject_id in subject_ids:
            e, d = self.get_subject(subject_id)
            if e<0:
                logging.error(f"error at {subject_id} !!!")
                logging.error(d)
                # break
            elif e==1:
                count_crawled += 1
            if count_crawled  and count_crawled%10==0:
                t = random.randint(3, 5)
                logging.info(f"crawled {count_crawled}, randomly sleep {t}s")
                time.sleep(t)
            count_success += 1
        logging.info(f"end {taskname}.. {count_success}/{len(subject_ids)} craweled")

    def process_subjects(self, version="1"):
        collection: Collection = self.db.subject
        findfilter = {
            "version": version,
        }
        for s in collection.find(findfilter):
            subject_id = s["subject_id"]
            title, titlecn = s['info']['name'], s['info']['name_cn']
            collection.update_one({
                "subject_id": subject_id, "version": version
            }, { "$set": { 
                    "title": title,
                    "titlecn": titlecn
                } 
            })

spyder = SpyderBangumi()
# spyder.get_calendar()
# spyder.get_subject(310263)
spyder.get_subjects_calendar()

# spyder.process_subjects()
