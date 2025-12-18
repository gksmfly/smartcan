# app/db/init_db.py

from app.db.session import Base, engine
from app.db import models  # noqa: F401  # 모델들을 메타데이터에 등록하기 위해 import만

def init() -> None:
    print("creating tables...")
    Base.metadata.create_all(bind=engine)
    print("done.")

if __name__ == "__main__":
    init()