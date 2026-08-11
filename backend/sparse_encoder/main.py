"""Uvicorn application 入口。"""

from sparse_encoder.service import create_app


app = create_app()
