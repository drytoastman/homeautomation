export PATH="$PATH:/usr/local/bin"
eval $(docker-machine env)
docker stop home_web_1
docker run --rm -v ssldata:/etc/letsencrypt -p 443:443 certbot/certbot renew
docker start home_web_1
