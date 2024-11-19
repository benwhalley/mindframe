# deploy


poetry2setup > setup.py
poetry lock
poetry export -o requirements.txt --without-hashes

# git commit -a -m "deploy"
# git add tag