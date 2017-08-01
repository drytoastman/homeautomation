eval $(docker-machine env)
docker run --rm -v ssldata:/etc/ssl -v $(pwd):/backup:ro nginx:alpine ash -c "cd /etc/ssl && rm -rf * && tar xvf /backup/ssldata.tgz && chmod -R root:root /etc/ssl"

