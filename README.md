# film-store-backend

## Python Virtual Environment

### Activate using Python:
``` 
source venv/bin/activate
python app.py
```
### Activate using Flask CLI:
``` 
source venv/bin/activate
export FLASK_DEBUG=1 
flask run --port=3001  
```
### Deactivate:
```
deactivate 
```

For full-stack development, run both servers concurrently:
1. Terminal 1: `cd backend && source venv/bin/activate && python app.py`
2. Terminal 2: `cd frontend && npm start
