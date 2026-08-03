import os
from dotenv import load_dotenv
load_dotenv()
class MineruToken:
    mineru_token = os.getenv('MINERU_TOKEN')