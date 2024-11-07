

Using psql, make a database and user:

```
create database mindframe;
CREATE USER mindframe_customuser WITH PASSWORD 'YOUR_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE mfexample TO mindframe_customuser;
```


Then load the example dataset

```bash
# edit .env to make sure access keys are set correcltly for LLM provider
cp .env-example .env

./manage.py migrate
./manage.py loaddata  fixtures/exampledb.json  
./manage.py dumpdata --indent=2  fixtures/exampledb.json  
```

Make an admin user:

```bash
./manage.py createsuperuser --username admin
```


Then run the server for the backend:

```bash
./manage.py runserver
```

And open http://localhost:8000/admin/ to login with the admin user.



## Using the chatbot

To use the chatbot, you need to run the frontend server:

```bash
python gradio_app.py
```

And then open  <http://127.0.0.1:7861>


At the moment the chatbot defaults to interacting with the most recent TreatmentSession

