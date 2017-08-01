FROM boot2docker/boot2docker:17.06.0-ce
COPY 98-usbserial.rules $ROOTFS/etc/udev/rules.d
RUN /tmp/make_iso.sh
CMD ["cat", "boot2docker.iso"]
