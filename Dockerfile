FROM tensorflow/tensorflow:1.15.2-gpu-py3

RUN apt-get update && \
    apt-get install -y \
        libsm6 \
        libxrender1 \
        libxext6

RUN pip install --upgrade pip

RUN pip install opencv-python

WORKDIR root
