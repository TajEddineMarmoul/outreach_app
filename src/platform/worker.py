from __future__ import annotations

import os

from redis import Redis
from rq import Queue, Worker


QUEUE_NAME = "outreach-send"


def run_worker() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL is required to run the send worker.")
    connection = Redis.from_url(redis_url)
    worker = Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    run_worker()
