from dotenv import load_dotenv
load_dotenv()
import os
org_id = os.getenv('ORGID')
openai_key = os.getenv('SECRETKEY')
from dialogtree import Dialog
if __name__ == "__main__":
    import re
    def match_zipcode(answer, context):
        print('zipcode', answer)
        if (zipcode:= re.match(r"\d{5}", answer)[0]):
            context["zipcode"] = zipcode
            return zipcode
        else:
            return None
    dialog = Dialog(treefile="example.xml", functions={'match_zipcode': match_zipcode}, openai_key=openai_key, org_id=org_id, model="gpt-4")
    dialog.start()