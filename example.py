org_id = '' #Replace this with the secret that I sent you over email
openai_key = '' #Replace this with the secret that I set you over email
from dialogtree import Dialog
if __name__ == "__main__":
    dialog = Dialog(treefile="example.xml", functions={}, openai_key=openai_key, org_id=org_id, model="gpt-4")
    dialog.start()