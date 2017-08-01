eval $(docker-machine env)
docker run --rm -v ssldata:/etc/ssl:ro -v $(pwd):/backup nginx:alpine ash -c "cd /etc/ssl && tar czvf /backup/ssldata.tgz ."

