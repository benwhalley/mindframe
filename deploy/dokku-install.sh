# limactl start --name=dokku https://raw.githubusercontent.com/thewisenerd/lima-templates/master/22.04.yaml
# lima dokku

sudo apt-get update
sudo apt-get install


# update docker stuff to avoid dokku install failing
# this is necessary on my ubuntu azure images, but may not always be needed
# sudo apt-get install ca-certificates curl gnupg
# sudo install -m 0755 -d /etc/apt/keyrings
# curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
# sudo chmod a+r /etc/apt/keyrings/docker.gpg
# echo \
#   "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
#   "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
#   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
# sudo apt-get update
# sudo apt-get install docker-compose-plugin


# install dokku
wget -NP . https://dokku.com/install/v0.35.18/bootstrap.sh
sudo DOKKU_TAG=v0.35.18 bash bootstrap.sh


# usually your key is already available under the current user's `~/.ssh/authorized_keys` file
cat ~/.ssh/authorized_keys | sudo dokku ssh-keys:add admin

# you can use any domain you already have access to
# this domain should have an A record or CNAME pointing at your server's IP
dokku domains:set-global dokku.llemma.net





# PLUGINS

sudo dokku plugin:install https://github.com/dokku/dokku-postgres.git --name postgres
sudo dokku plugin:install https://github.com/dokku/dokku-redis.git --name redis

sudo dokku plugin:install https://github.com/dokku/dokku-letsencrypt.git
sudo dokku letsencrypt:cron-job --add # <- To enable auto-renew


sudo dokku plugin:install https://github.com/dokku/dokku-maintenance.git maintenance

sudo dokku plugin:install https://github.com/dokku-community/dokku-apt

sudo dokku plugin:install https://github.com/crisward/dokku-require.git require


# dokku plugin:install https://github.com/dokku/dokku.git proxy 0.35.18






# DB MANAGEMENT

# for restore
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt install postgresql-17 postgresql-client-17
export PATH="/usr/lib/postgresql/17/bin:$PATH"
