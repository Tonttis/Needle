"""Bounded shared in-memory preview cache; concurrent listeners reuse one fetch.
Bytes never enter the metadata database. YouTube files retain existing disk policy.
"""
import time,threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
class AudioCache:
 def __init__(self,loader,max_bytes=64*1024*1024,ttl=900):
  self.loader=loader;self.limit=max_bytes;self.ttl=ttl;self.bytes=0
  self.items=OrderedDict();self.jobs={};self.lock=threading.Lock();self.workers=ThreadPoolExecutor(max_workers=4)
 def get(self,key,song):
  with self.lock:
   item=self.items.get(key)
   if item and time.monotonic()-item[0]<self.ttl:
    self.items.move_to_end(key);return item[1]
   if key not in self.jobs:self.jobs[key]=self.workers.submit(self._load,key,song)
   future=self.jobs[key]
  return future.result(timeout=110)
 def _load(self,key,song):
  try:
   result=self.loader(song);size=len(result[0])
   with self.lock:
    old=self.items.pop(key,None)
    if old:self.bytes-=len(old[1][0])
    if size<=self.limit:
     while self.items and self.bytes+size>self.limit:
      _,value=self.items.popitem(last=False);self.bytes-=len(value[1][0])
     self.items[key]=(time.monotonic(),result);self.bytes+=size
   return result
  finally:
   with self.lock:self.jobs.pop(key,None)
