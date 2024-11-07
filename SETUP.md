
First pull the repo:

```bash
git clone https://github.com/benwhalley/mindframe/
```

Copy and edit `.env` to make sure access keys are set correcltly for LLM provider:

```bash
cd mindframe/src
cp .env-example .env
```


Install the requirements from pyproject.toml:

```bash
pip install poetry
poetry shell
poetry install
```


Use `psql` to make a database and user with full access:

```sql
create database mindframe;
CREATE USER mindframe_customuser WITH PASSWORD 'YOUR_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE mfexample TO mindframe_customuser;
```

(Note, in production we would restrict access somewhat)


Then load the example dataset:

```bash
./manage.py migrate
./manage.py loaddata  fixtures/exampledb.json  
./manage.py dumpdata --indent=2  fixtures/exampledb.json  
```


Make a django admin user to allow access to the backend:

```bash
./manage.py createsuperuser --username admin
```

Then run the server for the backend to check it works:

```bash
./manage.py runserver
```

And open http://localhost:8000/admin/ to login with the admin user.



## Using the chatbot

To use the chatbot, you need to run the frontend server:

```bash
python gradio_app.py
```

And then open  <http://127.0.0.1:8001>



# Running both servers together

In production we'll use a Procfile to run both servers together in a heroku-like buildpack (ie. using dokku).

You can test this using honcho (which is a process orchestration package)

```bash
# first stop any runsever or gradio instances
honcho start
```

Now, both servers should be running together. You can access the chatbot on localhost port 8001, and the web backend on localhost port 8000.


