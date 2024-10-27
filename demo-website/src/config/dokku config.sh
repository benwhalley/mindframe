
# Set the profiles for development
dokku config:set mindframe COMPOSE_PROFILES=postgres,redis,assets,web,worker --no-restart

# Enable debug mode in development
dokku config:set mindframe DEBUG=true --no-restart

dokku config:set mindframe ALLOWED_HOSTS=mindframe.llemma.net  --no-restart

# Set Docker restart policy to no
dokku config:set mindframe DOCKER_RESTART_POLICY=no --no-restart
