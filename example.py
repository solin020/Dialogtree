from dotenv import load_dotenv
load_dotenv()
import os
org_id = os.getenv('ORGID')
openai_key = os.getenv('SECRETKEY')
from dialogtree import Dialog
if __name__ == "__main__":
    dialog = Dialog(treefile="example.xml", functions={}, openai_key=openai_key, org_id=org_id, model="gpt-4")
    dialog.start()