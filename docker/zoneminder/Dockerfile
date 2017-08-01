FROM debian:stretch-slim

RUN echo "deb http://www.deb-multimedia.org stretch main non-free" >> /etc/apt/sources.list
RUN apt-get update && apt-get --allow-unauthenticated install -y deb-multimedia-keyring && apt-get update \
    && apt-get install -y vlc-plugin-base \
    && apt-get install -y --no-install-recommends zoneminder \
    && apt-get clean

RUN adduser www-data video
RUN a2disconf serve-cgi-bin
RUN a2enmod cgi rewrite
RUN chown -R www-data:www-data /usr/share/zoneminder
RUN echo "[Date]\ndate.timezone = America/Los_Angeles" >> /etc/php/7.0/apache2/php.ini
RUN ln -fs /usr/share/zoneinfo/America/Los_Angeles /etc/localtime
RUN dpkg-reconfigure -f noninteractive tzdata

COPY zm.conf  /etc/zm
COPY start.pl /
CMD ["/start.pl"]
