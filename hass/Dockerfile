# Staged build, requires docker 17.05 or later
FROM python:3.6.2 as build

# Basic hass virtual env /code for code and /hass for virtualenv
WORKDIR /code
RUN python3 -mvenv /hass
RUN git clone https://github.com/home-assistant/home-assistant && cd home-assistant && git checkout 0.49.1 && /hass/bin/pip install .

# Other dependencies I use
# WARNING!  This is only for my own installation, others may need another modules that I am not installing
RUN /hass/bin/pip install  \
    aiohttp_cors==0.5.3 \
    hbmqtt==0.8  \
    paho-mqtt==1.3.0 \
    pydispatcher==2.0.5 \
    pymysql \
    pyserial==3.1.1 \
    sqlalchemy==1.1.11 \
    zeroconf==0.19.1 

# Custom zwave bit (stock python lib, just a patch to the .so file)
RUN apt-get update && apt-get install libudev-dev
RUN git clone https://github.com/OpenZWave/python-openzwave
RUN git clone http://github.com/drytoastman/open-zwave python-openzwave/openzwave
RUN cd python-openzwave && git checkout v0.4.0.31 && /hass/bin/python3 setup.py install --flavor=dev

# Now make a clean image with just the stuff we need
FROM python:3.6.2-slim
WORKDIR /hass
COPY --from=build /hass .
CMD [ "/hass/bin/hass", "--config", "/config" ]
