#!/bin/zsh

IMAGE_NAME=arijun/dblidarnet

xhost +

docker run -it --rm \
    --privileged \
    --env=QT_X11_NO_MITSHM=1 \
    --env=DISPLAY=$DISPLAY \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --gpus all \
    --name dblidarnet \
    --volume="${PWD}:/root/" \
    ${IMAGE_NAME} \
    bash
