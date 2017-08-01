# Create custom boot2docker for docker-toolbox installs so we can tag select USB devices all the way through
docker build -t myb2d .
docker run --rm myb2d > boot2docker.iso
