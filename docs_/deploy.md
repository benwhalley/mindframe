# deploy



# on package
poetry2setup > setup.py


# on project
poetry lock && poetry export -o requirements.txt --without-hashes

# git commit -a -m "deploy"
# git add tag
